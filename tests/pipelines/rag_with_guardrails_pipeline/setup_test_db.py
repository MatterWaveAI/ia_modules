"""Setup test database with sample documents for SQL RAG."""
import asyncio
from pathlib import Path
import sys

# Add paths
current_dir = Path(__file__).parent
tests_dir = current_dir.parent.parent
ia_modules_dir = tests_dir.parent
sys.path.insert(0, str(ia_modules_dir))

from nexusql import DatabaseManager  # noqa: E402


async def setup_test_database():
    """Create test database with sample documents."""
    # Use SQLite for simplicity
    db_url = "sqlite:///./test_documents.db"

    db_manager = DatabaseManager(db_url)
    await db_manager.initialize(apply_schema=False)

    # Create documents table
    # Drop existing table
    await db_manager.execute_async("DROP TABLE IF EXISTS documents")

    # Create table
    await db_manager.execute_async("""
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Insert sample documents
    documents = [
            {
                "title": "Introduction to Neural Networks",
                "content": """Neural networks are computing systems inspired by biological neural networks.
                They consist of interconnected nodes (neurons) organized in layers. The basic types include
                feedforward networks, convolutional neural networks (CNNs), recurrent neural networks (RNNs),
                and transformers. Transformers use attention mechanisms to process sequential data and power
                models like GPT and BERT.""",
                "category": "AI"
            },
            {
                "title": "Attention Mechanism Explained",
                "content": """The attention mechanism allows neural networks to focus on specific parts of the
                input when producing output. In transformers, self-attention computes relationships between all
                positions in a sequence. The mechanism uses queries, keys, and values to compute weighted
                representations. Multi-head attention allows the model to attend to different aspects
                simultaneously.""",
                "category": "AI"
            },
            {
                "title": "Machine Learning Basics",
                "content": """Machine learning is a subset of artificial intelligence that enables systems to
                learn from data. Main types include supervised learning (learning from labeled data),
                unsupervised learning (finding patterns in unlabeled data), and reinforcement learning
                (learning through trial and error). Key concepts include overfitting, underfitting, and
                cross-validation.""",
                "category": "AI"
            },
            {
                "title": "Deep Learning Applications",
                "content": """Deep learning has revolutionized many fields including computer vision, natural
                language processing, speech recognition, and autonomous vehicles. CNNs excel at image tasks,
                RNNs and transformers handle sequential data, and GANs generate realistic synthetic data.
                Applications range from medical diagnosis to game playing.""",
                "category": "AI"
            },
            {
                "title": "Python Programming Guide",
                "content": """Python is a high-level programming language known for its simplicity and
                readability. It supports multiple programming paradigms including procedural, object-oriented,
                and functional programming. Python is widely used in data science, web development, automation,
                and scientific computing. Key features include dynamic typing, garbage collection, and extensive
                standard library.""",
                "category": "Programming"
            },
            {
                "title": "Database Systems Overview",
                "content": """Database systems store and manage structured data. Relational databases use SQL
                and tables with defined schemas. NoSQL databases include document stores, key-value stores,
                graph databases, and column-family stores. Modern databases support transactions, indexing,
                replication, and distributed architectures for scalability.""",
                "category": "Databases"
            },
        ]

    for doc in documents:
        await db_manager.execute_async(
            "INSERT INTO documents (title, content, category) VALUES (:title, :content, :category)",
            doc
        )

    print(f"Created test database: {db_url}")
    print(f"Inserted {len(documents)} sample documents")
    print("\nSample documents:")
    for i, doc in enumerate(documents, 1):
        print(f"  {i}. {doc['title']} ({doc['category']})")

    await db_manager.close()


if __name__ == "__main__":
    asyncio.run(setup_test_database())
