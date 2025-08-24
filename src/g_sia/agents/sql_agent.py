"""
SQL Agent for G-SIA that converts natural language queries to secure SQL.

This agent uses LangChain SQL toolkit to generate safe, parameterized queries
while enforcing compliance and security constraints.
"""

import os
import sys
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv

from langchain.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain.schema import BaseOutputParser

# Add src directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from g_sia.core.database import get_database_manager

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SafeSQLOutputParser(BaseOutputParser):
    """Custom output parser that ensures SQL queries are safe."""
    
    def parse(self, text: str) -> str:
        """Parse and validate SQL output."""
        # Extract SQL from the response
        lines = text.strip().split('\n')
        sql_lines = []
        
        in_sql = False
        for line in lines:
            line = line.strip()
            if line.upper().startswith(('SELECT', 'WITH')):
                in_sql = True
            
            if in_sql:
                sql_lines.append(line)
                
            # Stop at semicolon or end of SQL statement
            if in_sql and (line.endswith(';') or line.upper().startswith(('LIMIT', 'ORDER BY'))):
                break
        
        sql = ' '.join(sql_lines).strip()
        
        # Remove trailing semicolon if present
        if sql.endswith(';'):
            sql = sql[:-1]
            
        return sql


class SQLAgent:
    """
    SQL Agent that converts approved natural language queries to secure SQL.
    """
    
    def __init__(
        self,
        model: str = "gpt-5-mini",
        temperature: float = 0.0,
        max_query_length: int = 2000,
        allowed_tables: Optional[List[str]] = None
    ):
        """
        Initialize SQL Agent.
        
        Args:
            model: OpenAI model to use
            temperature: LLM temperature setting
            max_query_length: Maximum allowed query length
            allowed_tables: List of allowed table names (None = all tables)
        """
        self.model = model
        self.temperature = temperature
        self.max_query_length = max_query_length
        self.allowed_tables = allowed_tables or []
        
        # Initialize database connection
        self.db_manager = get_database_manager()
        
        # Initialize LangChain SQL database
        self._init_sql_database()
        
        # Initialize LLM
        self.llm = ChatOpenAI(model=model, temperature=temperature)
        
        # Initialize SQL generation prompt
        self._init_sql_prompt()
        
        # Security constraints
        self.forbidden_keywords = [
            'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE', 'TRUNCATE',
            'GRANT', 'REVOKE', 'EXEC', 'EXECUTE', 'CALL'
        ]
        
        # PII fields that should be avoided or aggregated
        self.pii_fields = [
            'SSN', 'DRIVERS', 'PASSPORT', 'FIRST', 'LAST', 'MAIDEN',
            'ADDRESS', 'EMAIL', 'PHONE'
        ]
    
    def _init_sql_database(self):
        """Initialize LangChain SQL database connection."""
        try:
            engine = self.db_manager.get_engine()
            self.sql_db = SQLDatabase(engine)
            logger.info("SQL database connection initialized for LangChain")
        except Exception as e:
            logger.error(f"Failed to initialize SQL database: {e}")
            raise
    
    def _init_sql_prompt(self):
        """Initialize SQL generation prompt template."""
        self.sql_prompt = ChatPromptTemplate.from_template("""
You are a PostgreSQL expert working with a healthcare database containing synthetic patient data. 
Your job is to convert natural language questions into safe, compliant PostgreSQL queries.

CRITICAL DATABASE RULES:
1. This is a PostgreSQL database - use PostgreSQL-specific syntax and functions
2. ALL column names are case-sensitive and use double quotes (e.g., "PATIENT", "DESCRIPTION")
3. Use ILIKE for case-insensitive text matching (PostgreSQL-specific)
4. For rounding numbers, use CAST(value AS DECIMAL(10,2)) instead of ROUND()
5. For age calculations, use EXTRACT(YEAR FROM AGE(CURRENT_DATE, "BIRTHDATE"))

CRITICAL SECURITY RULES:
1. ONLY generate SELECT queries - no INSERT, UPDATE, DELETE, DROP, etc.
2. NEVER return personally identifiable information (PII) like SSN, names, addresses
3. For demographic queries, use aggregation (COUNT, AVG, SUM) instead of individual records
4. Always use LIMIT to prevent large result sets (max 1000 rows)
5. Use proper WHERE clauses to filter data appropriately

COMPLIANCE REQUIREMENTS:
- Patient privacy must be maintained at all times
- Aggregate data when possible (counts, averages, percentages)
- Avoid queries that could identify specific individuals
- Use statistical summaries rather than individual records

KEY TABLE RELATIONSHIPS:
- patients table: "Id" (primary key), "GENDER", "BIRTHDATE", "STATE", etc.
- conditions table: "PATIENT" (foreign key to patients."Id"), "DESCRIPTION"
- encounters table: "PATIENT" (foreign key to patients."Id"), "DESCRIPTION"
- medications table: "PATIENT" (foreign key to patients."Id"), "DESCRIPTION"

IMPORTANT COLUMN NAMES (always use with double quotes):
- Patient ID: "Id" in patients table, "PATIENT" in other tables
- Medical conditions: "DESCRIPTION" in conditions table
- Patient demographics: "GENDER", "BIRTHDATE", "STATE" in patients table

DATABASE SCHEMA INFORMATION:
{schema_info}

QUESTION: {question}

Generate a PostgreSQL query that answers the question while following all security and compliance rules.
Use proper PostgreSQL syntax, correct column names with double quotes, and appropriate JOINs when needed.
Return only the SQL query without any explanations, markdown formatting, or additional text.

EXAMPLES:
- For diabetes patients: SELECT COUNT(DISTINCT "PATIENT") FROM conditions WHERE "DESCRIPTION" ILIKE '%diabetes%'
- For age by gender: SELECT "GENDER", CAST(AVG(EXTRACT(YEAR FROM AGE(CURRENT_DATE, "BIRTHDATE"))) AS DECIMAL(10,2)) FROM patients WHERE "BIRTHDATE" IS NOT NULL GROUP BY "GENDER"
""")
    
    def validate_query_security(self, query: str) -> Dict[str, Any]:
        """
        Validate SQL query for security compliance.
        
        Args:
            query: SQL query to validate
            
        Returns:
            Validation result with details
        """
        query_upper = query.upper()
        violations = []
        warnings = []
        
        # Check for forbidden keywords
        for keyword in self.forbidden_keywords:
            if keyword in query_upper:
                violations.append(f"Forbidden SQL operation: {keyword}")
        
        # Check for PII field access without aggregation
        for pii_field in self.pii_fields:
            if pii_field in query_upper:
                # Check if it's in an aggregation function
                if not any(agg in query_upper for agg in ['COUNT(', 'SUM(', 'AVG(', 'GROUP BY']):
                    violations.append(f"Direct access to PII field: {pii_field}")
                else:
                    warnings.append(f"PII field {pii_field} used in aggregation - ensure compliance")
        
        # Check query length
        if len(query) > self.max_query_length:
            violations.append(f"Query too long: {len(query)} > {self.max_query_length}")
        
        # Check for LIMIT clause (should be present for safety)
        if 'LIMIT' not in query_upper and 'COUNT(' not in query_upper:
            warnings.append("Query should include LIMIT clause to prevent large result sets")
        
        # Check table access if restrictions are in place
        if self.allowed_tables:
            for table in self.allowed_tables:
                if table.upper() not in query_upper:
                    continue
            # If we get here, query might access forbidden tables
            # This is a simplified check - more sophisticated parsing would be needed
        
        return {
            "is_safe": len(violations) == 0,
            "violations": violations,
            "warnings": warnings,
            "query_length": len(query)
        }
    
    def generate_sql(self, natural_language_query: str) -> Dict[str, Any]:
        """
        Generate SQL query from natural language.
        
        Args:
            natural_language_query: User's question in natural language
            
        Returns:
            Dictionary containing SQL query and metadata
        """
        try:
            logger.info(f"Generating SQL for query: '{natural_language_query}'")
            
            # Get database schema information
            schema_info = self.sql_db.get_table_info()
            
            # Generate SQL using the prompt template
            prompt = self.sql_prompt.format(
                schema_info=schema_info,
                question=natural_language_query
            )
            
            response = self.llm.invoke(prompt)
            
            # Extract SQL from response
            sql_query = response.content.strip()
            
            # Clean up the SQL query
            if sql_query.startswith('```sql'):
                sql_query = sql_query.replace('```sql', '').replace('```', '').strip()
            elif sql_query.startswith('```'):
                sql_query = sql_query.replace('```', '').strip()
            
            # Remove any trailing semicolon
            if sql_query.endswith(';'):
                sql_query = sql_query[:-1]
            
            # Remove any explanatory text - keep only the SQL
            lines = sql_query.split('\n')
            sql_lines = []
            for line in lines:
                line = line.strip()
                if line.upper().startswith(('SELECT', 'WITH', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'LIMIT', 'HAVING')):
                    sql_lines.append(line)
                elif sql_lines and line and not line.startswith(('--', '/*', '//')):
                    # Continue SQL if we're already in a SQL block
                    sql_lines.append(line)
            
            if sql_lines:
                sql_query = ' '.join(sql_lines)
            
            final_result = sql_query
            
            # Validate security
            security_check = self.validate_query_security(sql_query) if sql_query else {
                "is_safe": False,
                "violations": ["No SQL query generated"],
                "warnings": [],
                "query_length": 0
            }
            
            success = bool(sql_query and security_check["is_safe"])
            if not success:
                error_details = []
                if not sql_query:
                    error_details.append("No SQL query was generated from the response")
                if sql_query and not security_check["is_safe"]:
                    error_details.append(f"Security violations: {', '.join(security_check['violations'])}")
                logger.error(f"SQL generation failed: {'; '.join(error_details)}")
            
            return {
                "success": success,
                "sql_query": sql_query,
                "original_query": natural_language_query,
                "security_validation": security_check,
                "intermediate_steps": [],
                "model_used": self.model,
                "final_result": final_result,
                "error": "; ".join(error_details) if not success and 'error_details' in locals() else None
            }
            
        except Exception as e:
            logger.error(f"Failed to generate SQL query: {e}")
            return {
                "success": False,
                "error": str(e),
                "original_query": natural_language_query,
                "sql_query": None
            }
    
    def execute_sql(self, sql_query: str) -> Dict[str, Any]:
        """
        Execute SQL query safely.
        
        Args:
            sql_query: SQL query to execute
            
        Returns:
            Query execution results
        """
        try:
            # Final security validation
            security_check = self.validate_query_security(sql_query)
            
            if not security_check["is_safe"]:
                return {
                    "success": False,
                    "error": "Query failed security validation",
                    "violations": security_check["violations"],
                    "sql_query": sql_query
                }
            
            # Execute query using database manager
            result = self.db_manager.execute_safe_query(sql_query)
            
            # Add security information to result
            result["security_validation"] = security_check
            result["executed_by"] = "sql_agent"
            
            if result.get("success", False):
                logger.info(f"SQL query executed successfully. Rows returned: {result.get('row_count', 0)}")
            else:
                logger.error(f"SQL query execution failed: {result.get('error', 'Unknown error')}")
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to execute SQL query: {e}")
            return {
                "success": False,
                "error": str(e),
                "sql_query": sql_query
            }
    
    def process_query(self, natural_language_query: str) -> Dict[str, Any]:
        """
        Complete process: generate SQL from natural language and execute it.
        
        Args:
            natural_language_query: User's question in natural language
            
        Returns:
            Complete query processing results
        """
        try:
            # Step 1: Generate SQL
            sql_result = self.generate_sql(natural_language_query)
            
            if not sql_result["success"]:
                return sql_result
            
            sql_query = sql_result["sql_query"]
            
            # Step 2: Execute SQL
            execution_result = self.execute_sql(sql_query)
            
            # Combine results
            return {
                "success": execution_result["success"],
                "original_query": natural_language_query,
                "generated_sql": sql_query,
                "sql_generation": sql_result,
                "execution_result": execution_result,
                "data": execution_result.get("data", []),
                "row_count": execution_result.get("row_count", 0),
                "security_validation": execution_result.get("security_validation", {}),
                "warnings": execution_result.get("security_validation", {}).get("warnings", [])
            }
            
        except Exception as e:
            logger.error(f"Failed to process query: {e}")
            return {
                "success": False,
                "error": str(e),
                "original_query": natural_language_query
            }
    
    def get_database_info(self) -> Dict[str, Any]:
        """Get information about the database schema."""
        return self.db_manager.get_table_info()


def main():
    """Test SQL Agent functionality."""
    try:
        # Initialize SQL Agent
        agent = SQLAgent()
        
        # Test queries
        test_queries = [
            "How many patients are in the database?",
            "What are the most common medical conditions?",
            "Show me the average age of patients by gender",
            "How many encounters happened in 2023?",
        ]
        
        print("🧪 Testing SQL Agent")
        print("=" * 50)
        
        for query in test_queries:
            print(f"\nQuery: {query}")
            print("-" * 40)
            
            result = agent.process_query(query)
            
            if result["success"]:
                print(f"✅ Generated SQL: {result['generated_sql']}")
                print(f"📊 Rows returned: {result['row_count']}")
                
                if result.get("warnings"):
                    print(f"⚠️  Warnings: {', '.join(result['warnings'])}")
                
                # Show sample data
                if result.get("data") and len(result["data"]) > 0:
                    print("📋 Sample results:")
                    for i, row in enumerate(result["data"][:3]):
                        print(f"  {i+1}. {row}")
            else:
                print(f"❌ Error: {result.get('error', 'Unknown error')}")
                if result.get("violations"):
                    print(f"🚫 Violations: {', '.join(result['violations'])}")
    
    except Exception as e:
        print(f"❌ Test failed: {e}")


if __name__ == "__main__":
    main()
