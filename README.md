# statementSync

**statementSync** is an automated bank statement extraction and synchronization tool designed to streamline the process of managing financial transactions. By leveraging advanced technologies such as Python, Notion API, and OpenAI's language models, statementSync efficiently extracts essential transaction data from PDF bank statements and seamlessly integrates them into organized Notion databases. This solution caters to individuals and organizations seeking to maintain accurate and up-to-date financial records with minimal manual intervention.

## Features

- **Automated PDF Processing**: Downloads and reads PDF bank statements using PyMuPDF, extracting relevant textual data for further analysis.
- **Intelligent Data Extraction**: Utilizes OpenAI's GPT-3.5-turbo model to accurately parse and extract critical transaction details, including Transaction Date, Product Name, Price, and Category.
- **Dynamic Categorization**: Treats the `Category` field as a rich text property, allowing for flexible and accurate categorization of transactions without predefined constraints.
- **Notion Integration**: Connects to Notion's API to create and manage databases, ensuring that each respondent has a dedicated database for their transactions. This includes automatic creation of necessary database properties and handling of multiple respondents.
- **Error Handling & Validation**: Implements robust error handling mechanisms to manage issues during PDF processing, data extraction, and Notion API interactions. Ensures data integrity through comprehensive validation steps.
- **Scalability**: Designed to handle multiple PDF entries across various respondents, making it suitable for both individual and enterprise-level financial management.

## Technologies Used

- **Python**
- **PyMuPDF (fitz)**
- **Notion API**
- **OpenAI GPT-3.5-turbo**
- **dotenv**
- **requests**
- **dateutil**

## Installation
 **Create a Virtual Environment**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

**Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

**Setup Environment Variables**

    Create a `.env` file in the root directory and add the following:
    ```env
    NOTION_API_KEY=your_notion_api_key
    OPENAI_API_KEY=your_openai_api_key
    ```

## Usage
Run the script using Python:
python statementSync.py


```mermaid
flowchart TD
    A[Start] --> B[Load Environment Variables]
    B --> C[Initialize Notion & OpenAI Clients]

    C --> D[Query Main Database]
    D --> E[Get Unprocessed PDFs]

    E --> F{PDF Found?}
    F -->|No| Z[End]
    F -->|Yes| G[Get Respondent Info]

    G --> H{Existing Database?}
    H -->|Yes| J[Use Existing DB]
    H -->|No| I[Create New DB]
    I --> J

    J --> K[Process PDF]
    K --> L[Extract Text]
    L --> M[Analyze with GPT]
    M --> N[Format Data]

    N --> O[Populate Database]
    O --> P{More PDFs?}
    P -->|Yes| E
    P -->|No| Z

```

```mermaid
classDiagram
    class MainProcess{
        +load_env()
        +init_clients()
        +process_pdfs()
    }

    class PDFProcessing{
        +read_pdf()
        +analyze_pdf_content()
        +process_single_pdf()
    }

    class DatabaseManagement{
        +check_existing_database()
        +create_new_database()
        +populate_database()
    }

    class DataTracking{
        +processed_pdfs
        +get_pdf_entries()
        +mark_as_processed()
    }

    MainProcess --> PDFProcessing
    MainProcess --> DatabaseManagement
    MainProcess --> DataTracking

```
