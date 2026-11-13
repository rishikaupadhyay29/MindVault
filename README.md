# 🧠 MindVault

### Your Personal AI-Powered Second Brain

MindVault is an AI-powered personal knowledge management system designed to help you capture, organize, connect, and rediscover information.

It transforms scattered notes, documents, and web bookmarks into an intelligent, searchable knowledge space using semantic search, vector embeddings, and Retrieval-Augmented Generation (RAG).

**Don't just store what you learn. Connect it, understand it, and rediscover it.**

---

## ✨ Features

### 📚 Knowledge Management

- Create, edit, and organize personal notes.
- Maintain a centralized Knowledge Library.
- Organize information using tags.
- Attach existing Library documents to notes.
- Filter and sort notes, documents, and bookmarks.
- Mark important items as Favorites.

### 📁 Collections

- Create personalized collections to organize knowledge.
- Add notes, documents, and bookmarks to collections.
- Add the same Library item to multiple collections.
- Rename and delete collections.
- Remove items from collections without deleting them from the Library.
- View collection contents and item counts.

### 📄 Document Intelligence

- Upload PDF, TXT, and Markdown documents.
- Automatically extract document content.
- Split content into searchable text chunks.
- Generate and store vector embeddings.

### 🔖 Links & Bookmarks

- Save website URLs directly to your Knowledge Library.
- Automatically extract webpage titles and readable content.
- Add custom titles and tags.
- Preserve original webpage URLs.
- Index bookmarked content for semantic retrieval.

### 🔍 Semantic Search

- Search knowledge by meaning rather than exact keywords.
- Retrieve relevant information from indexed notes and documents.
- Use vector similarity to discover related content.

### 🤖 AI Companion

- Ask questions about your personal knowledge base.
- Retrieve relevant context from saved information.
- Generate context-aware responses using RAG.
- Use local AI inference through Ollama.

### 🌌 Knowledge Universe

- Explore relationships between notes through an interactive 2D knowledge graph.
- Discover potentially connected ideas using embedding similarity.

---

## 🛠️ Technology Stack

| Component      | Technologies                  |
| -------------- | ----------------------------- |
| Frontend       | HTML, CSS, JavaScript         |
| Backend        | Python, FastAPI               |
| Database       | PostgreSQL, pgvector          |
| ORM            | SQLAlchemy                    |
| Migrations     | Alembic                       |
| Embeddings     | Sentence Transformers, MiniLM |
| AI Inference   | Ollama                        |
| Language Model | Qwen 2.5 (1.5B)               |
| Web Extraction | HTTPX, HTML parsing           |
| Testing        | Pytest, jsdom                 |

---

## 🏗️ Architecture

MindVault follows a modular architecture in which a FastAPI server serves both the frontend and backend APIs.

### Knowledge Processing Workflow

1. Users create notes, upload documents, or save website bookmarks.
2. The backend extracts readable content.
3. Content is divided into smaller text chunks.
4. Sentence Transformers generates vector embeddings.
5. PostgreSQL with pgvector stores knowledge and embeddings.
6. Semantic retrieval identifies relevant information.
7. The AI Companion uses retrieved context to generate grounded responses.

### System Architecture

```text
                       MindVault
                           |
                +----------+----------+
                |                     |
             Frontend              FastAPI
          HTML/CSS/JS                 |
                               +------+------+
                               |             |
                             Routes       Services
                               |             |
                     +---------+---------+   |
                     |         |         |   |
                   Notes   Collections  Search
                     |         |         |
                  Favorites   Library   Graph
                     |         |         |
                     +---------+---------+
                               |
                         PostgreSQL
                          + pgvector
                               |
                       Vector Retrieval
                               |
                         AI Companion
                               |
                            Ollama
```

---

## 🧠 AI & Retrieval-Augmented Generation

MindVault combines semantic retrieval with Retrieval-Augmented Generation (RAG).

- **Text Extraction:** Extracts readable content from supported documents and webpages.
- **Chunking:** Splits content into manageable text segments.
- **Embedding Generation:** Converts text into numerical vector representations.
- **Vector Storage:** Stores embeddings using PostgreSQL and pgvector.
- **Similarity Search:** Retrieves relevant chunks based on semantic similarity.
- **Contextual Generation:** Passes retrieved context to a local language model through Ollama.

This enables the AI Companion to answer questions using the user's own saved knowledge.

---

## 📂 Project Structure

```text
MindVault/
│
├── backend/
│   ├── app/
│   │   ├── routes/
│   │   ├── services/
│   │   ├── models.py
│   │   └── main.py
│   │
│   ├── migrations/
│   │   └── versions/
│   ├── tests/
│   ├── requirements.txt
│   └── docker-compose.yml
│
├── frontend/
│   └── index.html
│
├── tools/
├── README.md
├── BUILD_STATUS.md
└── .gitignore
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Docker Desktop
- Ollama
- Git

### 1. Clone the repository

```bash
git clone https://github.com/rishikaupadhyay29/MindVault.git
cd MindVault
```

### 2. Start PostgreSQL with pgvector

From the project root:

```bash
docker compose -f backend/docker-compose.yml up -d
```

### 3. Install Ollama and download the language model

Install Ollama from:

https://ollama.com

Download the model:

```bash
ollama pull qwen2.5:1.5b
```

### 4. Set up the Python environment

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 5. Configure environment variables

```powershell
copy .env.example .env
```

Configure the database connection, Ollama settings, and other required environment variables in `.env`.

Generate a secure secret key locally:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Set the generated value as `SECRET_KEY`.

**Never commit your `.env` file or expose authentication tokens.**

### 6. Run database migrations

```powershell
alembic upgrade head
```

### 7. Start the application

```powershell
uvicorn app.main:app --reload --port 8000
```

Open the application:

http://localhost:8000

API documentation:

http://localhost:8000/docs

Create an account to start building your personal knowledge library.

---

## 🧪 Testing

Run the backend test suite:

```bash
pytest
```

Run the real embedding model test:

```bash
pytest -m real_model
```

The real-model test requires downloading the embedding model.

---

## 💻 Local AI Execution

MindVault uses Ollama for local AI inference and Sentence Transformers for embeddings.

The core knowledge-processing workflow is designed to run locally rather than depending on a hosted LLM API.

This architecture provides a foundation for private, locally executed AI-powered knowledge management.

---

## 🔮 Future Roadmap

- [ ] Improved knowledge graph exploration.
- [ ] AI-powered document and webpage summarization.
- [ ] AI-generated flashcards.
- [ ] Daily journal and reading list.
- [ ] Improved knowledge recommendations.
- [ ] Enhanced document preview and organization.
- [ ] Browser-based knowledge capture.
- [ ] Production deployment and cloud infrastructure.

---

## 👩‍💻 Author

**Rishika Upadhyay**

B.Tech – Computer Science & Engineering

Interested in Artificial Intelligence, Machine Learning, and building practical AI-powered applications.

---

## 📜 License

A license has not yet been specified.

---

_MindVault — Don't just store what you learn. Connect it, understand it, and rediscover it._
