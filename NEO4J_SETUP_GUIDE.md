# Neo4j + LangChain Graph RAG Setup Guide

This guide walks you through setting up a **production-grade Neo4j Graph RAG system** for your compliance-aware AI chatbot.

## 🎯 Why Neo4j Over NetworkX?

| Feature | NetworkX (Previous) | Neo4j (Current) |
|---------|-------------------|-----------------|
| **Graph Size** | Limited to memory | Handles billions of nodes |
| **Query Language** | Python code | Cypher (declarative) |
| **Persistence** | File-based | ACID transactions |
| **Performance** | O(n) traversals | Indexed lookups |
| **Visualization** | Matplotlib | Neo4j Browser |
| **Concurrent Access** | Single process | Multi-user |
| **Graph Algorithms** | Basic | Advanced (PageRank, etc.) |

## 🚀 Installation Options

### Option A: Neo4j Desktop (Recommended for Development)

1. **Download Neo4j Desktop**
   ```bash
   # Visit: https://neo4j.com/download/
   # Download for Windows/Mac/Linux
   ```

2. **Create a New Database**
   - Open Neo4j Desktop
   - Click "New" → "Create Project"
   - Click "Add" → "Local DBMS"
   - Set Name: `policy-compliance-db`
   - Set Password: `your_secure_password`
   - Version: Latest (5.x)

3. **Start the Database**
   - Click the "Start" button
   - Note the connection details (usually `bolt://localhost:7687`)

### Option B: Neo4j AuraDB (Cloud - Production)

1. **Create Free Account**
   ```bash
   # Visit: https://neo4j.com/aura/
   # Sign up for free tier
   ```

2. **Create Instance**
   - Choose "AuraDB Free"
   - Name: `policy-compliance`
   - Region: Choose closest to you
   - Save the generated password!

3. **Get Connection String**
   - Format: `neo4j+s://xxxxx.databases.neo4j.io`

### Option C: Docker (Advanced)

```bash
docker run \
    --name neo4j-policy \
    -p7474:7474 -p7687:7687 \
    -d \
    -v neo4j_data:/data \
    -v neo4j_logs:/logs \
    -v neo4j_import:/var/lib/neo4j/import \
    --env NEO4J_AUTH=neo4j/your_password \
    neo4j:latest
```

## ⚙️ Configuration

### 1. Update Your `.env` File

Create or update your `.env` file with Neo4j credentials:

```bash
# OpenAI Configuration  
OPENAI_API_KEY=your_openai_api_key_here

# Neo4j Configuration
NEO4J_URL=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your_secure_password

# For Neo4j AuraDB (Cloud):
# NEO4J_URL=neo4j+s://your-instance.databases.neo4j.io
# NEO4J_USERNAME=neo4j
# NEO4J_PASSWORD=your_aura_password
```

### 2. Verify Connection

Test your Neo4j connection:

```bash
# From Neo4j Desktop/Browser, run:
MATCH (n) RETURN count(n)
```

Should return `0` for a fresh database.

## 🏗️ Build the Neo4j Graph RAG System

### Step 1: Setup the System

```bash
cd Compliance-Aware-AI-Chatbot
python scripts/setup_neo4j_system.py --rebuild
```

Expected output:
```
🚀 Setting up Neo4j Graph RAG System
📁 Found 3 policy files:
  - CaliforniaConsumerPrivacyAct.pdf
  - GDPR.pdf
  - hipaa-simplification-201303.pdf

🔗 Connecting to Neo4j at bolt://localhost:7687...
✅ Connected to Neo4j at bolt://localhost:7687
🏗️ Building Neo4j Graph RAG system...
✅ Neo4j Graph RAG system setup completed successfully!
```

### Step 2: Test the System

```bash
python test_neo4j_system.py
```

This runs comprehensive tests across multiple compliance scenarios.

## 🔍 Exploring Your Graph

### Neo4j Browser

1. Open: http://localhost:7474
2. Login with your credentials
3. Try these queries:

```cypher
// View all entity types
MATCH (e:Entity) 
RETURN e.type, count(e) as count
ORDER BY count DESC

// Find HIPAA-related entities
MATCH (e:Entity {policy_type: 'HIPAA'})
RETURN e.name, e.description
LIMIT 10

// Explore relationships
MATCH (e1:Entity)-[r]->(e2:Entity)
RETURN e1.name, type(r), e2.name
LIMIT 20

// Find policy paths
MATCH path = (e1:Entity)-[*1..3]-(e2:Entity)
WHERE e1.name CONTAINS 'patient' 
  AND e2.name CONTAINS 'consent'
RETURN path
LIMIT 5
```

## 🧪 Advanced Testing

### Test Individual Components

```python
from g_sia.agents.neo4j_policy_agent import Neo4jPolicyAgent

# Initialize agent
agent = Neo4jPolicyAgent()

# Test compliance analysis
result = agent.get_policy_verdict("Can I access patient medical records?")
print(f"Verdict: {result['verdict']}")
print(f"Reasoning: {result['reasoning']}")

# Test relationship analysis  
relationships = agent.explain_policy_relationship("patient data", "consent")
print(f"Relationships: {relationships}")

# Get graph statistics
stats = agent.get_graph_statistics()
print(f"Graph stats: {stats}")
```

### Performance Testing

```bash
# Test with various query types
python -c "
from test_neo4j_system import test_neo4j_policy_analysis
import time

start = time.time()
test_neo4j_policy_analysis()
end = time.time()

print(f'Total test time: {end - start:.2f} seconds')
"
```

## 🔧 Troubleshooting

### Common Issues

**1. "Failed to connect to Neo4j"**
```bash
# Check if Neo4j is running
neo4j status

# Start Neo4j
neo4j start

# Check logs
neo4j console
```

**2. "Authentication failed"**
- Verify username/password in `.env`
- Reset password in Neo4j Desktop
- For AuraDB, check connection string format

**3. "No policy documents found"**
- Ensure PDFs are in `policy_corpus/` directory
- Check file permissions
- Verify PDF text extraction is working

**4. "Graph is empty after setup"**
- Check OpenAI API key is valid
- Verify PDF content is extractable
- Review setup logs for errors

### Performance Optimization

**For Large Datasets:**
```cypher
// Create additional indexes
CREATE INDEX entity_policy_type_idx FOR (e:Entity) ON (e.policy_type);
CREATE INDEX entity_importance_idx FOR (e:Entity) ON (e.importance);

// Monitor query performance
PROFILE MATCH (e:Entity) WHERE e.name CONTAINS 'patient' RETURN e;
```

**Memory Settings (neo4j.conf):**
```
dbms.memory.heap.initial_size=2G
dbms.memory.heap.max_size=4G
dbms.memory.pagecache.size=1G
```

## 📊 Expected Performance

With your PDF policy documents, expect:

- **Graph Size**: 200+ entities, 300+ relationships
- **Query Speed**: <500ms for most compliance queries  
- **Accuracy**: 85-95% on compliance classification
- **Memory Usage**: 100-500MB depending on document size

## 🔄 Migration from NetworkX

If you have existing NetworkX data:

1. **Keep both systems** during transition
2. **Compare results** between NetworkX and Neo4j
3. **Gradually migrate** queries to Neo4j
4. **Remove NetworkX** once confident

## 🎯 Next Steps

With Neo4j Graph RAG complete:

1. ✅ **Enhanced Policy Analysis**: More sophisticated relationship reasoning
2. ✅ **Scalable Architecture**: Handle larger policy corpora  
3. ✅ **Graph Visualization**: Explore policy relationships visually
4. ✅ **Advanced Queries**: Complex Cypher-based compliance checks

**Phase 3** will integrate this with:
- SQL Query Agent for database access
- Query Rewriter for compliance modifications
- LangGraph orchestration for complete workflow

## 🌟 Neo4j Graph RAG Advantages

Your system now provides:

- **🔗 Relationship Discovery**: Find hidden connections between policies
- **📊 Path Analysis**: Understand compliance reasoning chains  
- **🎯 Contextual Retrieval**: Better policy context for LLM analysis
- **🔍 Explainable AI**: Show why decisions were made
- **⚡ Performance**: Fast graph traversals at scale

Ready to explore your policy knowledge graph! 🚀
