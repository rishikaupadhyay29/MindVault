# MindVault 🧠

### Your Personal AI-Powered Second Brain

MindVault is an AI-powered personal knowledge management system that helps users capture, organize, connect, and rediscover information. It transforms scattered notes and documents into an intelligent, searchable knowledge space using semantic search, vector embeddings, and Retrieval-Augmented Generation (RAG).

Instead of simply storing information, MindVault helps you explore what you already know.

## ✨ Features

- **Knowledge Management:** Create, edit, and organize personal notes.
- **Document Intelligence:** Upload PDF, TXT, and Markdown documents and automatically extract their content.
- **Semantic Search:** Discover information based on meaning rather than exact keywords.
- **AI Companion:** Ask questions about your knowledge base and receive context-aware answers with source references.
- **Document Attachments:** Attach Library documents to notes without duplicating files or embeddings.
- **Knowledge Universe:** Explore relationships between notes through an interactive 2D knowledge graph.
- **Related Notes:** Discover potentially connected ideas using embedding similarity.
- **User Authentication:** Secure, account-based access to personal knowledge.
- **System Diagnostics:** Monitor application services and document-processing status.

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
| Testing        | Pytest, jsdom                 |

## 🏗️ Architecture

MindVault follows a modular architecture in which a FastAPI server serves both the frontend and backend API.

### Knowledge Processing Workflow

1. Users create notes or upload documents.
2. The backend extracts and processes document content.
3. Content is divided into smaller text chunks.
4. Sentence Transformers generates vector embeddings.
5. PostgreSQL with pgvector stores the knowledge and embeddings.
6. Semantic retrieval identifies relevant information.
7. The AI Companion uses retrieved context to generate grounded responses.

## 🧠 AI & Retrieval-Augmented Generation

MindVault combines semantic retrieval with Retrieval-Augmented Generation (RAG).

- **Text Extraction:** Extracts readable content from supported documents.
- **Chunking:** Splits content into manageable text segments.
- **Embedding Generation:** Converts text into numerical vector representations.
- **Vector Storage:** Stores embeddings using PostgreSQL and pgvector.
- **Similarity Search:** Retrieves relevant chunks based on semantic similarity.
- **Contextual Generation:** Passes retrieved information to a local language model through Ollama.

This enables the AI Companion to answer questions using the user's own saved knowledge.

## 📁 Project Structure

```text
MindVault/
│
├── backend/
│   ├── app/
│   │   ├── routes/
│   │   ├── services/
│   │   ├── models.py
│   │   └── main.py
│   ├── migrations/
│   ├── tests/
│   ├── requirements.txt
│   └── docker-compose.yml
│
├── frontend/
│   └── index.html
│
├── tools/
├── README.md
└── BUILD_STATUS.md
```

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Docker Desktop
- Ollama
- Git

### Installation

**1. Clone the repository**

```bash
git clone https://github.com/rishikaupadhyay29/MindVault.git
cd MindVault
```

**2. Start PostgreSQL with pgvector**

```bash
docker compose -f backend/docker-compose.yml up -d
```

**3. Download the language model**

```bash
ollama pull qwen2.5:1.5b
```

Install Ollama from https://ollama.com first.

**4. Set up the Python environment**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**5. Configure environment variables**

```powershell
copy .env.example .env
```

Configure your database settings and generate a secure `SECRET_KEY` in the `.env` file.

**6. Run database migrations**

```bash
alembic upgrade head
```

**7. Start the application**

```bash
uvicorn app.main:app --port 8000
```

Open http://localhost:8000 in your browser and create an account.

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

## 💻 Local AI Execution

MindVault uses Ollama for local AI inference and CPU-based embeddings, making it suitable for development on systems without a dedicated GPU.

The core knowledge-processing workflow is designed to run locally rather than depending on a hosted LLM API.

## 🔮 Future Roadmap

- [ ] Link and bookmark management
- [ ] Improved knowledge graph exploration
- [ ] Advanced AI-powered knowledge discovery
- [ ] Browser-based knowledge capture
- [ ] Enhanced document preview and organization
- [ ] More intelligent recommendations and connections

## 👩‍💻 Author

**Rishika Upadhyay**

B.Tech – Computer Science & Engineering

Interested in Artificial Intelligence, Machine Learning, and building practical AI-powered applications.

---

_MindVault — Don't just store what you learn. Connect it, understand it, and rediscover it._
