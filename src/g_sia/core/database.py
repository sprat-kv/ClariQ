"""
Database connection and utilities for G-SIA.

This module provides secure database connections and utilities for the SQL Agent.
"""

import os
import logging
from typing import Optional, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages secure database connections for G-SIA.
    """
    
    def __init__(self):
        """Initialize database manager."""
        self.engine: Optional[Engine] = None
        self._connection_params = self._load_connection_params()
    
    def _load_connection_params(self) -> Dict[str, str]:
        """Load database connection parameters from environment."""
        params = {
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "host": os.getenv("DB_HOST", "localhost"),
            "port": os.getenv("DB_PORT", "5432"),
            "database": os.getenv("DB_NAME")
        }
        
        # Validate required parameters
        missing_params = [key for key, value in params.items() if not value]
        if missing_params:
            raise ValueError(
                f"Missing required database parameters: {', '.join(missing_params)}. "
                "Please check your .env file."
            )
        
        return params
    
    def get_engine(self) -> Engine:
        """
        Get database engine, creating it if necessary.
        
        Returns:
            SQLAlchemy engine instance
        """
        if self.engine is None:
            self.engine = self._create_engine()
        
        return self.engine
    
    def _create_engine(self) -> Engine:
        """Create SQLAlchemy engine with proper configuration."""
        try:
            # URL-encode password to handle special characters
            encoded_password = quote_plus(self._connection_params["password"])
            
            connection_string = (
                f"postgresql+psycopg2://"
                f"{self._connection_params['user']}:{encoded_password}@"
                f"{self._connection_params['host']}:{self._connection_params['port']}/"
                f"{self._connection_params['database']}"
            )
            
            engine = create_engine(
                connection_string,
                # Security and performance settings
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,  # Validate connections before use
                pool_recycle=3600,   # Recycle connections every hour
                echo=False  # Set to True for SQL debugging
            )
            
            # Test connection
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            logger.info("Database connection established successfully")
            return engine
            
        except Exception as e:
            logger.error(f"Failed to create database engine: {e}")
            raise
    
    def test_connection(self) -> bool:
        """
        Test database connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            engine = self.get_engine()
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM patients LIMIT 1"))
                count = result.scalar()
                logger.info(f"Database connection test successful. Found {count} patients.")
                return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def get_table_info(self) -> Dict[str, Any]:
        """
        Get information about database tables and their schemas.
        
        Returns:
            Dictionary containing table information
        """
        try:
            engine = self.get_engine()
            
            # Query to get table information
            table_query = text("""
                SELECT 
                    table_name,
                    column_name,
                    data_type,
                    is_nullable
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                ORDER BY table_name, ordinal_position
            """)
            
            with engine.connect() as conn:
                result = conn.execute(table_query)
                rows = result.fetchall()
            
            # Organize by table
            tables = {}
            for row in rows:
                table_name = row[0]
                if table_name not in tables:
                    tables[table_name] = {
                        "columns": [],
                        "sample_data": None
                    }
                
                tables[table_name]["columns"].append({
                    "name": row[1],
                    "type": row[2],
                    "nullable": row[3] == "YES"
                })
            
            # Get sample data for each table (first 3 rows)
            for table_name in tables.keys():
                try:
                    sample_query = text(f"SELECT * FROM {table_name} LIMIT 3")
                    with engine.connect() as conn:
                        sample_result = conn.execute(sample_query)
                        tables[table_name]["sample_data"] = [
                            dict(row._mapping) for row in sample_result.fetchall()
                        ]
                except Exception as e:
                    logger.warning(f"Could not get sample data for {table_name}: {e}")
                    tables[table_name]["sample_data"] = []
            
            return tables
            
        except Exception as e:
            logger.error(f"Failed to get table information: {e}")
            return {}
    
    def execute_safe_query(self, query: str, params: Optional[Any] = None) -> Dict[str, Any]:
        """
        Execute a query safely with proper error handling.
        
        Args:
            query: SQL query to execute
            params: Optional parameters for the query
            
        Returns:
            Dictionary containing results and metadata
        """
        try:
            engine = self.get_engine()
            
            with engine.connect() as conn:
                if params:
                    result = conn.execute(text(query), params)
                else:
                    result = conn.execute(text(query))
                
                # Handle different query types
                if result.returns_rows:
                    rows = result.fetchall()
                    columns = list(result.keys())
                    
                    return {
                        "success": True,
                        "data": [dict(zip(columns, row)) for row in rows],
                        "columns": columns,
                        "row_count": len(rows),
                        "query": query
                    }
                else:
                    return {
                        "success": True,
                        "message": f"Query executed successfully. Rows affected: {result.rowcount}",
                        "rows_affected": result.rowcount,
                        "query": query
                    }
                    
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "query": query
            }
    
    def close(self):
        """Close database connections."""
        if self.engine:
            self.engine.dispose()
            self.engine = None
            logger.info("Database connections closed")


# Global database manager instance
_db_manager = None

def get_database_manager() -> DatabaseManager:
    """Get global database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


def main():
    """Test database connection and show table information."""
    try:
        db = DatabaseManager()
        
        # Test connection
        print("Testing database connection...")
        if db.test_connection():
            print("✅ Database connection successful!")
            
            # Show table information
            print("\n📊 Database Schema Information:")
            tables = db.get_table_info()
            
            for table_name, info in tables.items():
                print(f"\n🔸 Table: {table_name}")
                print(f"  Columns: {len(info['columns'])}")
                for col in info['columns'][:5]:  # Show first 5 columns
                    print(f"    - {col['name']} ({col['type']})")
                if len(info['columns']) > 5:
                    print(f"    ... and {len(info['columns']) - 5} more columns")
                
                if info['sample_data']:
                    print(f"  Sample rows: {len(info['sample_data'])}")
        else:
            print("❌ Database connection failed!")
            
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
