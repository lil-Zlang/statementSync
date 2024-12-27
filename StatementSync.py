import os
import csv
from datetime import datetime
from io import BytesIO
import requests
from dotenv import load_dotenv
from notion_client import Client as NotionClient
import fitz  # PyMuPDF
from openai import OpenAI
from dateutil import parser

# Load environment variables from .env file
load_dotenv()

# Initialize Notion API client
notion = NotionClient(auth=os.getenv("NOTION_API_KEY"))
MAIN_DATABASE_ID = "main database ID"  # Replace with your actual main database ID
TARGET_PAGE_ID = " target page ID"  # Replace with your actual target page ID

# Initialize OpenAI API client
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY is not set in the environment variables.")

client = OpenAI(api_key=openai_api_key)

def read_pdf(pdf_url):
    """
    Downloads and reads the content of a PDF file using PyMuPDF.

    Args:
        pdf_url (str): The URL of the PDF file.

    Returns:
        str: Extracted text content from the PDF or an error message.
    """
    try:
        response = requests.get(pdf_url)
        response.raise_for_status()
        with BytesIO(response.content) as pdf_file:
            doc = fitz.open(stream=pdf_file, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
        return text
    except Exception as e:
        return f"Error reading PDF: {str(e)}"

def analyze_pdf_content(pdf_content, retries=3):
    """
    Uses OpenAI's GPT model to extract transaction data from PDF content.

    Args:
        pdf_content (str): The extracted text content from the PDF.
        retries (int): Number of retries allowed in case of failures.

    Returns:
        list: A list of dictionaries containing transaction data.
    """
    prompt_template = (
        "Analyze the following PDF content and extract the following information for each transaction:\n"
        "- Price\n"
        "- Product Name\n"
        "- Transaction Date\n"
        "- Category (e.g., Groceries, Utilities, Entertainment, etc.)\n\n"
        "Provide **only** the extracted data in a structured CSV format with headers: Transaction Date, Product Name, Price, Category.\n"
        "Do **not** include any additional text, explanations, or messages.\n\n"
        "Here is an example of the desired CSV format:\n"
        "```\n"
        "Transaction Date,Product Name,Price,Category\n"
        "2022-09-08,Example Product,100.00,Groceries\n"
        "2022-09-09,Another Product,200.50,Utilities\n"
        "```\n\n"
        "Now, based on the PDF content below, provide the CSV data accordingly.\n\n"
        f"PDF Content:\n{pdf_content}"
    )

    for attempt in range(1, retries + 1):
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt_template}],
                max_tokens=1500,
                temperature=0.2
            )
            assistant_message = response.choices[0].message.content.strip()

            # Extract CSV block
            csv_start = assistant_message.find("```\n")
            csv_end = assistant_message.find("```", csv_start + 4)
            if csv_start != -1 and csv_end != -1:
                csv_content = assistant_message[csv_start + 4:csv_end].strip()
            else:
                csv_content = assistant_message.strip()

            # Parse CSV content
            csv_file = BytesIO(csv_content.encode('utf-8'))
            reader = csv.DictReader(csv_file.read().decode('utf-8').splitlines())
            data = [row for row in reader]

            # Validate headers
            expected_headers = ["Transaction Date", "Product Name", "Price", "Category"]  # Updated headers
            if reader.fieldnames != expected_headers:
                raise ValueError(f"CSV headers do not match expected format. Found: {reader.fieldnames}")

            return data

        except Exception as e:
            print(f"Attempt {attempt} failed: {str(e)}")
            if attempt < retries:
                print("Retrying...")
            else:
                print("Max retries reached. Skipping this PDF.")
    return []

def ensure_database_properties(database_id):
    """
    Ensures that the Notion database has the required properties.
    """
    required_properties = {
        "Transaction Date": {
            "type": "date",
            "date": {}
        },
        "Product Name": {
            "type": "title",
            "title": {}
        },
        "Price": {
            "type": "number",
            "number": {
                "format": "dollar"
            }
        },
        "Category": {  
            "type": "rich_text",
            "rich_text": {}
        },
        "Processed": {
            "type": "checkbox",
            "checkbox": {}
        }
    }

    try:
        database = notion.databases.retrieve(database_id)
        existing_properties = database.get("properties", {})

        properties_to_add = {}
        for prop_name, prop_schema in required_properties.items():
            if prop_name not in existing_properties:
                properties_to_add[prop_name] = prop_schema
                print(f"Property '{prop_name}' is missing and will be added.")

        if properties_to_add:
            notion.databases.update(
                database_id=database_id,
                properties=properties_to_add
            )
            print("Missing properties have been added to the database.")
        else:
            print("All required properties already exist in the database.")

    except Exception as e:
        print(f"Error ensuring database properties: {str(e)}")

def check_existing_database(respondent_name, target_page_id):
    """
    Check if a database already exists for the respondent in the target location.

    Args:
        respondent_name (str): Name of the respondent
        target_page_id (str): ID of the target page

    Returns:
        str or None: Database ID if found, None if not found
    """
    try:
        # Use a unique naming convention for databases
        expected_title = f"{respondent_name}"

        response = notion.search(
            query=expected_title,
            filter={"property": "object", "value": "database"}
        ).get("results", [])

        # Check for exact title match and correct parent
        for db in response:
            if (
                db["parent"].get("type") == "page_id"
                and db["parent"].get("page_id") == target_page_id
                and db["title"][0]["text"]["content"] == expected_title
            ):
                print(f"Found existing database for {respondent_name}")
                return db["id"]

        return None  # Return None if no matching database is found

    except Exception as e:
        print(f"Error checking existing database: {str(e)}")
        return None

def create_new_database(respondent_name):
    """
    Creates a new database for a respondent.

    Args:
        respondent_name (str): Name of the respondent

    Returns:
        str: ID of the new database
    """
    try:
        # Unique database title
        database_title = f"{respondent_name}"

        new_database = notion.databases.create(
            parent={
                "type": "page_id",
                "page_id": TARGET_PAGE_ID  
            },
            title=[{
                "type": "text",
                "text": {"content": database_title}
            }],
            properties={
                "Transaction Date": {
                    "type": "date",
                    "date": {}
                },
                "Product Name": {
                    "type": "title",
                    "title": {}
                },
                "Price": {
                    "type": "number",
                    "number": {
                        "format": "dollar"
                    }
                },
                "Category": {  
                    "type": "rich_text",
                    "rich_text": {}
                },
                "Processed": {
                    "type": "checkbox",
                    "checkbox": {}
                }
            }
        )

        print(f"Created new database for {respondent_name} with ID: {new_database['id']}")
        return new_database["id"]

    except Exception as e:
        print(f"Error creating database for {respondent_name}: {str(e)}")
        return None

def get_pdf_entries(database_id):
    """
    Retrieves entries from the database that contain unprocessed PDFs.
    """
    try:
        results = []
        query = notion.databases.query(database_id=database_id)
        results.extend(query.get("results", []))

        # Process each entry to get PDF info
        pdf_entries = []
        for page in results:
            try:
                properties = page.get("properties", {})
                if "upload your bank statement" in properties:
                    pdf_files = properties["upload your bank statement"]["files"]

                    for pdf_file in pdf_files:
                        # Check if 'Processed' is False or not set
                        processed = properties.get("Processed", {}).get("checkbox", False)
                        if not processed:
                            respondent_name = "Unknown Respondent"
                            respondent_property = properties.get("Respondent", {})
                            created_by = respondent_property.get("created_by", {})
                            if isinstance(created_by, dict):
                                respondent_name = created_by.get("name", "Unknown Respondent")
                            
                            pdf_entries.append({
                                "page_id": page["id"],
                                "pdf_file": pdf_file,
                                "pdf_url": pdf_file["file"]["url"],
                                "respondent_name": respondent_name
                            })
                            print(f"Found new unprocessed PDF: {pdf_file.get('name')} for Respondent: {respondent_name}")
                        else:
                            print(f"Skipping already processed PDF: {pdf_file.get('name')}")
            except Exception as e:
                print(f"Error processing page: {str(e)}")
                continue

        return pdf_entries

    except Exception as e:
        print(f"Error querying database: {str(e)}")
        return []

def mark_pdf_as_processed(page_id):
    """
    Marks a PDF as processed by setting the 'Processed' checkbox to True.

    Args:
        page_id (str): The ID of the Notion page containing the PDF.
    """
    try:
        notion.pages.update(
            page_id=page_id,
            properties={
                "Processed": {
                    "checkbox": True
                }
            }
        )
        print(f"Marked page {page_id} as processed.")
    except Exception as e:
        print(f"Error marking page {page_id} as processed: {str(e)}")

def upload_transactions_to_notion(data, database_id):
    """
    Uploads transaction data directly to the specified Notion database.

    Args:
        data (list): List of dictionaries containing transaction data.
        database_id (str): Notion database ID.
    """
    uploaded_count = 0
    skipped_count = 0

    for row in data:
        try:
            # Convert date to ISO 8601 format
            date_str = row.get("Transaction Date", "")
            if not date_str:
                print(f"Missing 'Transaction Date' in row: {row}. Skipping row.")
                skipped_count += 1
                continue

            try:
                # Use dateutil for flexible parsing
                formatted_date = parser.parse(date_str).strftime("%Y-%m-%d")
            except ValueError:
                print(f"Invalid date format '{date_str}'. Skipping row.")
                skipped_count += 1
                continue

            product_name = row.get("Product Name", "").strip()
            price_str = row.get("Price", "").strip()
            category = row.get("Category", "").strip()  # Extracted Category

            if not product_name or not price_str or not category:  # Include Category in validation
                print(f"Missing 'Product Name', 'Price', or 'Category' in row: {row}. Skipping row.")
                skipped_count += 1
                continue

            # Sanitize and convert price to float
            try:
                price = float(price_str.replace(',', '').replace('$', ''))
            except ValueError:
                print(f"Invalid price format '{price_str}' in row: {row}. Skipping row.")
                skipped_count += 1
                continue

            # Create the page with correct property names and types
            properties = {
                "Transaction Date": {
                    "date": {"start": formatted_date}
                },
                "Product Name": {
                    "title": [{"text": {"content": product_name}}]
                },
                "Price": {
                    "number": price
                },
                "Category": {
                    "rich_text": [
                        {
                            "text": {
                                "content": category
                            }
                        }
                    ]
                }
            }

            notion.pages.create(
                parent={"database_id": database_id},
                properties=properties,
            )
            uploaded_count += 1

        except Exception as e:
            print(f"Error uploading row to Notion: {str(e)}")
            skipped_count += 1

    print(f"Uploaded {uploaded_count} rows to Notion.")
    print(f"Skipped {skipped_count} rows due to errors.")

def process_pdfs():
    """
    Processes unprocessed PDFs, extracts data, uploads to Notion, and marks PDFs as processed.
    """
    print("Fetching PDF entries from Notion database...")
    pdf_entries = get_pdf_entries(MAIN_DATABASE_ID)
    if not pdf_entries:
        print("No PDF entries found in the database.")
        return

    # Group PDFs by respondent
    respondent_pdfs = {}
    for entry in pdf_entries:
        respondent = entry["respondent_name"]
        if respondent not in respondent_pdfs:
            respondent_pdfs[respondent] = []
        respondent_pdfs[respondent].append(entry)

    # Process each respondent's PDFs
    for respondent, pdfs in respondent_pdfs.items():
        print(f"\nProcessing Respondent: {respondent}")
        # Check if a database exists for this respondent
        existing_db_id = check_existing_database(respondent, TARGET_PAGE_ID)
        if not existing_db_id:
            # Create a new database for the respondent
            existing_db_id = create_new_database(respondent)
            if not existing_db_id:
                print(f"Failed to create database for {respondent}. Skipping.")
                continue
        else:
            print(f"Using existing database for {respondent} with ID: {existing_db_id}")

        # Process each PDF for this respondent
        for pdf_entry in pdfs:
            try:
                page_id = pdf_entry["page_id"]
                pdf_file = pdf_entry["pdf_file"]
                pdf_url = pdf_entry["pdf_url"]
                pdf_name = pdf_file.get("name", "Extracted Transactions")
                print(f"Processing PDF: {pdf_name} from page ID {page_id}...")

                pdf_content = read_pdf(pdf_url)
                if pdf_content.startswith("Error"):
                    print(pdf_content)
                    continue

                extracted_data = analyze_pdf_content(pdf_content)

                # Debug print to see the structure of extracted data
                print("Extracted data structure:", extracted_data)

                if not extracted_data:
                    print(f"No valid data extracted from PDF in page ID {page_id}.")
                    continue

                # Validate and clean each item before adding to all_extracted_data
                cleaned_data = []
                for item in extracted_data:
                    if not isinstance(item, dict):
                        print(f"Skipping non-dictionary item: {item}")
                        continue

                    # Create a new dict with only the required fields
                    cleaned_item = {
                        "Transaction Date": item.get("Transaction Date", ""),
                        "Product Name": item.get("Product Name", ""),
                        "Price": item.get("Price", ""),
                        "Category": item.get("Category", "")  
                    }

                    # Only add if all required fields have values
                    if all(cleaned_item.values()):
                        cleaned_data.append(cleaned_item)
                    else:
                        print(f"Skipping incomplete data: {cleaned_item}")

                if cleaned_data:
                    # Upload transactions to the respondent's database
                    upload_transactions_to_notion(cleaned_data, existing_db_id)
                else:
                    print("No valid data to upload.")

                # After successful processing, mark the PDF as processed
                mark_pdf_as_processed(page_id)

            except Exception as e:
                print(f"Error processing PDF from page ID {pdf_entry['page_id']}: {str(e)}")
                continue

def main():
    # Ensure the main database has the correct properties
    ensure_database_properties(MAIN_DATABASE_ID)

    # Process PDFs and upload transactions
    process_pdfs()

if __name__ == "__main__":
    main()
