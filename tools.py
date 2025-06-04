# For Google Sheets
from typing import Any, Dict, Optional
from google.oauth2.service_account import Credentials # Example for service account
from googleapiclient.discovery import build
import os
from google.adk.tools import FunctionTool
import re # Import regular expressions


SHEETS_SERVICE_ACCOUNT_KEY_PATH = os.getenv("SHEETS_SERVICE_ACCOUNT_KEY_PATH") # Path to your service account JSON
USER_EMAIL_TO_SHARE_WITH = os.getenv("USER_EMAIL_TO_SHARE_WITH") # Email of the user to make owner of created files

def _get_sheets_service():
    """Helper function to authenticate and build Sheets and Drive API service clients."""
    # IMPORTANT: Implement proper authentication. Service account is common for backend services.
    # Ensure your service account has permissions to edit Google Sheets.
    # You might need to share the target Google Sheet with the service account's email address.
    # Also needs Drive API permissions if sharing.
    
    print(f"DEBUG: Value of SHEETS_SERVICE_ACCOUNT_KEY_PATH from env: '{SHEETS_SERVICE_ACCOUNT_KEY_PATH}'") # Debug print
    # Example using service account credentials:
    if not SHEETS_SERVICE_ACCOUNT_KEY_PATH:
        print("ERROR: _get_sheets_service - SHEETS_SERVICE_ACCOUNT_KEY_PATH environment variable is not set or is empty. Please check your .env file.")
        return None
    
    # Determine if the path from .env is absolute or relative
    if os.path.isabs(SHEETS_SERVICE_ACCOUNT_KEY_PATH):
        service_account_file_path = SHEETS_SERVICE_ACCOUNT_KEY_PATH
    else:
        # If relative, assume it's relative to the current file's directory (tools.py) for robustness
        base_dir = os.path.dirname(os.path.abspath(__file__))
        service_account_file_path = os.path.join(base_dir, SHEETS_SERVICE_ACCOUNT_KEY_PATH)

    
    print(f"INFO: _get_sheets_service - Attempting to load service account credentials from: {service_account_file_path}") 
    try:
            if not os.path.exists(service_account_file_path):
                print(f"ERROR: _get_sheets_service - Service account file not found at: {service_account_file_path}")
                return None
            
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive.file', # Scope for Drive API to manage permissions
                'https://www.googleapis.com/auth/documents' # Scope for Google Docs API
            ]
            creds = Credentials.from_service_account_file(
                service_account_file_path,
                scopes=scopes
            )
            sheets_service = build('sheets', 'v4', credentials=creds)
            drive_service = build('drive', 'v3', credentials=creds)
            docs_service = build('docs', 'v1', credentials=creds) # Build Docs service
            print("INFO: _get_sheets_service - Google Sheets, Drive, and Docs services created successfully.")
            return sheets_service, drive_service, docs_service
    except Exception as e:
        print(f"ERROR: _get_sheets_service - Failed to create Google Sheets service: {e}")
        return None
    

def export_trip_plan_to_google_sheet(
    financial_data: Dict[str, float], # Expects keys like "Flights", "Hotels", "Itinerary", "Food", "Budget"
    source: str,
    destination: str,
    financial_summary: str,  # Add this parameter
    spreadsheet_id: Optional[str] = None,
    spreadsheet_title: Optional[str] = "New Travel Plan",
    append_data: bool = False # New parameter to control append behavior
) -> Dict[str, Any]:
    """
    Exports a financial plan to a Google Sheet.
    Creates a tab named "Finance Planner" with columns for different cost categories,
    total estimated cost, budget, remaining/surplus amount, source, and destination.
    Also includes a column for the AI-generated financial summary.
    The financial_data dictionary contains the cost breakdown and budget.
    Source and destination are passed as separate string arguments.
    If append_data is True and spreadsheet_id is provided, data is appended to the "Finance Planner" tab.
    """
    services = _get_sheets_service()
    if not services or not all(services): # Check all three services
        return {"status": "error", "message": "Google API services (Sheets, Drive, or Docs) not available."}
    sheets_service, drive_service, _ = services # Docs service not used in this function

    sheet_id_to_use = spreadsheet_id
    actual_spreadsheet_title = spreadsheet_title if spreadsheet_title else "Finance Planner"
    new_sheet_created_url = None

    if not sheet_id_to_use: # If no sheet ID provided, always create a new one
        try:
            append_data = False # Cannot append to a sheet that doesn't exist yet
            # Create a new spreadsheet
            spreadsheet_body = {
                'properties': {
                    'title': actual_spreadsheet_title
                }
            }
            print(f"INFO: Attempting to create new spreadsheet with title: {actual_spreadsheet_title}")
            spreadsheet = sheets_service.spreadsheets().create(body=spreadsheet_body).execute()
            sheet_id_to_use = spreadsheet.get('spreadsheetId')
            new_sheet_created_url = spreadsheet.get('spreadsheetUrl')
            print(f"INFO: Created new spreadsheet with ID: {sheet_id_to_use}, URL: {new_sheet_created_url}")


            # Share the newly created sheet
            if sheet_id_to_use and USER_EMAIL_TO_SHARE_WITH:
                try:
                    permission = {
                        # Grant ownership to the specified user
                        'type': 'user',
                        'role': 'writer', # Changed from 'owner' to 'writer'
                        'emailAddress': USER_EMAIL_TO_SHARE_WITH
                    }
                    drive_service.permissions().create(fileId=sheet_id_to_use, body=permission, sendNotificationEmail=False).execute() # Removed transferOwnership
                    print(f"INFO: Shared spreadsheet {sheet_id_to_use} with {USER_EMAIL_TO_SHARE_WITH} as writer.")
                except Exception as e_share:
                    print(f"WARNING: Failed to share spreadsheet {sheet_id_to_use} with {USER_EMAIL_TO_SHARE_WITH}: {str(e_share)}")
        except Exception as e:
            print(f"ERROR: Failed to create new spreadsheet: {str(e)}")
            return {"status": "error", "message": f"Failed to create new spreadsheet: {str(e)}"}

    if not sheet_id_to_use:
        return {"status": "error", "message": "Spreadsheet ID is missing and new sheet creation might have failed."}

    finance_tab_name = "Finance Planner"

    try:
        sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=sheet_id_to_use).execute()
        existing_sheets = {sheet.get("properties", {}).get("title"): sheet.get("properties", {}).get("sheetId") for sheet in sheet_metadata.get('sheets', [])}
        finance_tab_sheet_id = None

        if finance_tab_name not in existing_sheets:
            add_sheet_request_body = {'requests': [{'addSheet': {'properties': {'title': finance_tab_name}}}]}
            response = sheets_service.spreadsheets().batchUpdate(spreadsheetId=sheet_id_to_use, body=add_sheet_request_body).execute()
            # Extract sheetId from response for the newly created tab
            new_sheet_properties = response.get('replies')[0].get('addSheet').get('properties')
            if new_sheet_properties:
                finance_tab_sheet_id = new_sheet_properties.get('sheetId')
                print(f"INFO: Created tab '{finance_tab_name}' with sheetId {finance_tab_sheet_id} in spreadsheet ID {sheet_id_to_use}.")
            else:
                # Fallback if sheetId cannot be extracted, though unlikely if creation succeeded
                print(f"WARNING: Created tab '{finance_tab_name}', but could not get its sheetId immediately. Formatting may not be applied.")
                # Re-fetch metadata to find it (less efficient but a fallback)
                sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=sheet_id_to_use).execute()
                existing_sheets = {
                    sheet.get("properties", {}).get("title"): sheet.get("properties", {}).get("sheetId") 
                    for sheet in sheet_metadata.get('sheets', []) if sheet.get("properties")}
                finance_tab_sheet_id = existing_sheets.get(finance_tab_name)
        else:
            finance_tab_sheet_id = existing_sheets[finance_tab_name]
            print(f"INFO: Tab '{finance_tab_name}' already exists with sheetId {finance_tab_sheet_id}.")

        # Clean up "Sheet1" if it exists and is not our finance_tab_name
        if finance_tab_sheet_id is not None: # Ensure we have a valid finance_tab_sheet_id
            try:
                all_sheets_metadata_response = sheets_service.spreadsheets().get(spreadsheetId=sheet_id_to_use, fields="sheets(properties(sheetId,title))").execute()
                all_sheets_properties = all_sheets_metadata_response.get('sheets', [])
                
                delete_sheet_requests = []
                for sheet_props_item in all_sheets_properties:
                    props = sheet_props_item.get('properties', {})
                    current_sheet_id_to_check = props.get('sheetId')
                    current_sheet_title_to_check = props.get('title')
                    
                    # Only delete "Sheet1" if it's not the actual finance_tab_sheet_id (e.g. if Finance Planner was renamed from Sheet1)
                    if current_sheet_title_to_check == "Sheet1" and current_sheet_id_to_check != finance_tab_sheet_id:
                        delete_sheet_requests.append({'deleteSheet': {'sheetId': current_sheet_id_to_check}})
                        print(f"INFO: Identified 'Sheet1' (ID: {current_sheet_id_to_check}) for deletion as it's not the target '{finance_tab_name}' tab.")

                if delete_sheet_requests:
                    sheets_service.spreadsheets().batchUpdate(
                        spreadsheetId=sheet_id_to_use,
                        body={'requests': delete_sheet_requests}
                    ).execute()
                    print(f"INFO: Successfully deleted 'Sheet1' tab(s) from spreadsheet ID {sheet_id_to_use}.")
            except Exception as e_delete_sheet1:
                print(f"WARNING: Could not clean up 'Sheet1' tab: {str(e_delete_sheet1)}")

        # Prepare data for the sheet
        headers = ["Source", "Destination", "Flights", "Hotels", "Itinerary", "Food", "Total Estimated Cost", "Budget", "Remaining/Surplus", "Financial Summary"]  # Add "Financial Summary"
        
        flight_cost = financial_data.get("Flights", 0.0)
        hotel_cost = financial_data.get("Hotels", 0.0)
        itinerary_cost = financial_data.get("Itinerary", 0.0)
        food_cost = financial_data.get("Food", 0.0)
        budget_amount = financial_data.get("Budget", 0.0)

        total_estimated_cost = flight_cost + hotel_cost + itinerary_cost + food_cost
        remaining_surplus = budget_amount - total_estimated_cost

        data_row = [source, destination, flight_cost, hotel_cost, itinerary_cost, food_cost, total_estimated_cost, budget_amount, remaining_surplus, financial_summary]  # Add financial_summary

        if append_data and spreadsheet_id: # Append only if ID is given and append is true
                # Append the data_row to the existing sheet
                body = {'values': [data_row]} # Note: data_row is already a list, wrap it in another list for rows
                result = sheets_service.spreadsheets().values().append(
                    spreadsheetId=sheet_id_to_use,
                    range=f"'{finance_tab_name}'!A1", # Append will find the first empty row
                    valueInputOption='USER_ENTERED',
                    insertDataOption='INSERT_ROWS',
                    body=body
                ).execute()
                print(f"INFO: Appended data to tab '{finance_tab_name}' in spreadsheet ID {sheet_id_to_use}.")
                # Formatting for appended rows might need specific handling if different from headers/first data row
                # For simplicity, this example doesn't re-apply all formatting to appended rows beyond what Sheets inherits.
                # Text wrapping for the new summary cell in the appended row will be applied.
        else:
                # Write headers and the first data_row (or overwrite)
                values_to_write = [headers, data_row]
                body = {'values': values_to_write}
                result = sheets_service.spreadsheets().values().update(
                    spreadsheetId=sheet_id_to_use,
                    range=f"'{finance_tab_name}'!A1", # Writing from cell A1
                    valueInputOption='USER_ENTERED',
                    body=body
                ).execute()
                print(f"INFO: Wrote/Overwrote data to tab '{finance_tab_name}' in spreadsheet ID {sheet_id_to_use}.")

            # Apply formatting if finance_tab_sheet_id is known
        if finance_tab_sheet_id:
                financial_summary_column_index = headers.index("Financial Summary") 
                active_formatting_requests = []

                if not append_data or not spreadsheet_id: # Only apply header formatting if not appending or if it's a new sheet
                    # Add request to make the header row bold
                    active_formatting_requests.append({
                        'updateCells': {
                            'rows': [{
                                'values': [ # For each cell in the header row
                                    {'userEnteredFormat': {'textFormat': {'bold': True}}}
                                ] * len(headers) # Apply to all header cells
                            }],
                            'fields': 'userEnteredFormat.textFormat.bold',
                            'range': {
                                'sheetId': finance_tab_sheet_id,
                                'startRowIndex': 0,  # Header row (0-indexed)
                                'endRowIndex': 1,    # Covers one row
                                'startColumnIndex': 0, # Starts from the first column
                                'endColumnIndex': len(headers) # Covers all header columns
                            }
                        }
                    })

                # Determine the row index for the financial summary cell to format
                # If appending, it's the last row written. If not, it's the first data row (index 1).
                summary_row_start_index = 1 # Default for new/overwrite
                if append_data and spreadsheet_id and result.get('updates') and result['updates'].get('updatedRange'):
                    # Try to get the actual appended row index from the response
                    # Format: 'SheetName'!A<start_row>:J<end_row>
                    updated_range_str = result['updates']['updatedRange']
                    match = re.search(r"A(\d+):", updated_range_str)
                    if match:
                        summary_row_start_index = int(match.group(1)) - 1 # API is 0-indexed
                
                # Apply text wrapping to the Financial Summary cell (current or appended row)
                active_formatting_requests.append({
                    'updateCells': {
                        'rows': [{'values': [{'userEnteredFormat': {'wrapStrategy': 'WRAP'}}]}],
                        'fields': 'userEnteredFormat.wrapStrategy',
                        'range': {
                            'sheetId': finance_tab_sheet_id,
                            'startRowIndex': summary_row_start_index,
                            'endRowIndex': summary_row_start_index + 1,
                            'startColumnIndex': financial_summary_column_index,
                            'endColumnIndex': financial_summary_column_index + 1
                        }
                    }
                })
                if active_formatting_requests:
                    sheets_service.spreadsheets().batchUpdate(
                        spreadsheetId=sheet_id_to_use,
                        body={'requests': active_formatting_requests}
                    ).execute()
                    print(f"INFO: Applied formatting (text wrapping for summary, bold headers) to tab '{finance_tab_name}'.")

        return {
            "status": "success",
            "message": f"Financial plan exported to tab '{finance_tab_name}'. Cells updated: {result.get('updatedCells')}.",
            "spreadsheet_url": new_sheet_created_url if new_sheet_created_url else f"https://docs.google.com/spreadsheets/d/{sheet_id_to_use}"
        }
    except Exception as e:
        print(f"ERROR: Failed to write to Google Sheet '{sheet_id_to_use}': {str(e)}")
        return {"status": "error", "message": f"Failed to write to Google Sheet: {str(e)}"}


export_to_google_sheet_tool = FunctionTool(func=export_trip_plan_to_google_sheet)

def _generate_text_requests_with_markdown(text_content: str, start_index: int) -> (list, int): # type: ignore
    """
    Parses text_content for markdown (bold, italics, bullets) and generates Google Docs API requests.
    Returns a list of requests and the new current_index after this content.
    """
    requests = []
    current_doc_index = start_index

    for line_with_ending in text_content.splitlines(keepends=True):
        line_content = line_with_ending.rstrip('\r\n')
        has_newline = line_with_ending.endswith(('\n', '\r\n'))

        line_start_index_for_paragraph_styling = current_doc_index
        is_bullet_line = False

        # Handle bullet points
        bullet_marker_match = re.match(r"^(\*\s+)", line_content) # Only match lines starting with "* "
        if bullet_marker_match:
            is_bullet_line = True
            # Insert the bullet marker text itself, but don't style it yet
            # The createParagraphBullets will handle the visual bullet
            # We just need to insert the text content after the marker
            content_after_bullet = line_content[len(bullet_marker_match.group(1)):].lstrip()
            text_to_process_inline = content_after_bullet
        else:
            text_to_process_inline = line_content

        # Process inline markdown (bold, italics)
        # Regex to find **bold** or *italic* or _italic_
        # It captures the content inside the markdown
        parts = re.split(r'(\*\*.*?\*\*|\*.*?\*|_.*?_)', text_to_process_inline)
 
        for part in parts:
            if not part:
                continue
 
            is_bold_segment = False
            is_italic_segment = False
            actual_text_to_insert = part
 
            if part.startswith('**') and part.endswith('**') and len(part) > 4:
                actual_text_to_insert = part[2:-2]
                is_bold_segment = True
            elif (part.startswith('*') and part.endswith('*') and len(part) > 2) or \
                 (part.startswith('_') and part.endswith('_') and len(part) > 2):
                actual_text_to_insert = part[1:-1]
                is_italic_segment = True
 
            if actual_text_to_insert:
                requests.append({'insertText': {'location': {'index': current_doc_index}, 'text': actual_text_to_insert}})
                # Always apply text style to explicitly set/unset bold and italic for the segment
                requests.append({'updateTextStyle': {
                    'range': {'startIndex': current_doc_index, 'endIndex': current_doc_index + len(actual_text_to_insert)},
                    'textStyle': {
                        'bold': is_bold_segment,
                        'italic': is_italic_segment
                        # Other styles like underline, strikethrough, etc., default to false/unset
                        # unless explicitly handled.
                    },
                    'fields': "bold,italic" # Specify that we are updating bold and italic properties
                }})
                current_doc_index += len(actual_text_to_insert)
 
        # Add the newline character if the original line had one
        if has_newline:
            requests.append({'insertText': {'location': {'index': current_doc_index}, 'text': '\n'}})
            current_doc_index += 1
        # If it's a bullet line with no actual text content (e.g., "* "),
        # and it didn't have a newline from the source (meaning it's the last line of input),
        # we must insert a newline to make it a paragraph for the bullet style to apply correctly.
        elif is_bullet_line and not text_to_process_inline and not has_newline:
            requests.append({'insertText': {'location': {'index': current_doc_index}, 'text': '\n'}})
            current_doc_index += 1
 
        # Apply bullet paragraph style if it was a bullet line.
        # current_doc_index is now at the end of the paragraph (after its newline, if any).
        # line_start_index_for_paragraph_styling is at the beginning of the paragraph's text content.
        if is_bullet_line:
            if current_doc_index > line_start_index_for_paragraph_styling: # Ensure the paragraph has content
                requests.append({'createParagraphBullets': {
                    'range': {
                        'startIndex': line_start_index_for_paragraph_styling,
                        'endIndex': current_doc_index # This range includes the paragraph's own newline
                    },
                    'bulletPreset': 'BULLET_DISC_CIRCLE_SQUARE' # Or other presets
                }})
    return requests, current_doc_index

def export_trip_plan_to_google_doc(
    flight_data: str,
    hotel_data: str,
    itinerary_data: str,
    food_recommendations_data: Optional[str] = None, # New parameter for food recommendations
    document_title: Optional[str] = "Travel Plan Document"
) -> Dict[str, Any]:
    """
    Exports flight, hotel, and itinerary data to a new Google Doc,
    with each section under a respective heading.
    """
    services = _get_sheets_service() # Reusing this helper, it now returns docs_service too
    if not services or not all(services):
        return {"status": "error", "message": "Google API services (Sheets, Drive, or Docs) not available."}
    _, drive_service, docs_service = services

    new_doc_url = None
    doc_id = None

    try:
        # Create a new Google Doc
        doc_body = {'title': document_title}
        print(f"INFO: Attempting to create new Google Doc with title: {document_title}")
        doc = docs_service.documents().create(body=doc_body).execute()
        doc_id = doc.get('documentId')
        new_doc_url = f"https://docs.google.com/document/d/{doc_id}/edit"
        print(f"INFO: Created new Google Doc with ID: {doc_id}, URL: {new_doc_url}")

        # Share the newly created document
        if doc_id and USER_EMAIL_TO_SHARE_WITH:
            try:
                permission = {
                    # Grant ownership to the specified user
                    'type': 'user',
                         'role': 'writer', # Changed from 'owner' to 'writer'
                    'emailAddress': USER_EMAIL_TO_SHARE_WITH
                }
                drive_service.permissions().create(fileId=doc_id, body=permission, sendNotificationEmail=False).execute() # Removed transferOwnership
                print(f"INFO: Shared Google Doc {doc_id} with {USER_EMAIL_TO_SHARE_WITH} as writer.")
            except Exception as e_share:
                print(f"WARNING: Failed to share Google Doc {doc_id} with {USER_EMAIL_TO_SHARE_WITH}: {str(e_share)}")

        # Prepare content for the document
        requests = []
        current_index = 1 # Start inserting at the beginning of the document body

        sections = [
            ("Flights", flight_data),
            ("Hotels", hotel_data),
            ("Itinerary", itinerary_data),
        ]
        # Add food recommendations section if data is provided
        if food_recommendations_data:
            sections.append(("Food", food_recommendations_data))

        for title, data_content in sections:
            # Insert heading text
            heading_text = f"{title}\n"
            requests.append({
                'insertText': {
                    'location': {'index': current_index},
                    'text': heading_text
                }
            })
            # Apply Heading 1 style to the heading text
            requests.append({
                'updateParagraphStyle': {
                    'range': {
                        'startIndex': current_index,
                        'endIndex': current_index + len(heading_text) -1 # -1 because \n is part of this paragraph but style applies to text before it
                    },
                    'paragraphStyle': {
                        'namedStyleType': 'HEADING_1'
                    },
                    'fields': 'namedStyleType'
                }
            })
            # Apply Bold style to the heading text
            requests.append({
                'updateTextStyle': {
                    'range': {
                        'startIndex': current_index,
                        'endIndex': current_index + len(heading_text) - 1
                    },
                    'textStyle': {'bold': True},
                    'fields': 'bold'
                }
            })
            current_index += len(heading_text)

         # Generate requests for data content with bolding
            data_requests, new_current_index = _generate_text_requests_with_markdown(data_content, current_index)
            requests.extend(data_requests)
            current_index = new_current_index
            
            # Add a single newline for spacing after the section's data, if the data_content itself doesn't end with one.
            # The _generate_text_requests_with_markdown should handle newlines from data_content.
            if data_content and not data_content.endswith('\n'):
                requests.append({'insertText': {'location': {'index': current_index}, 'text': "\n"}})
                current_index += 1
        docs_service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
        print(f"INFO: Content written to Google Doc {doc_id}")

        return {
            "status": "success",
            "message": f"Trip plan exported to Google Doc: {document_title}",
            "document_url": new_doc_url,
            "document_id": doc_id
        }

    except Exception as e:
        print(f"ERROR: Failed to create or update Google Doc: {str(e)}")
        error_message = f"Failed to create or update Google Doc: {str(e)}"
        if doc_id and not new_doc_url: # If doc was created but content update failed
             error_message += f" Document was created with ID {doc_id} but content update failed."
        return {"status": "error", "message": error_message, "document_id": doc_id}

export_to_google_doc_tool = FunctionTool(func=export_trip_plan_to_google_doc)


def delete_google_file_by_id(file_id: str) -> Dict[str, Any]:
    """
    Deletes a file (like a Google Sheet or Google Doc) from Google Drive
    using its file ID. This action is permanent.
    """
    services = _get_sheets_service() # Reusing this helper
    if not services or not all(services):
        return {"status": "error", "message": "Google API services (Sheets, Drive, or Docs) not available."}
    _, drive_service, _ = services # We only need drive_service here

    try:
        print(f"INFO: Attempting to delete file with ID: {file_id}")
        drive_service.files().delete(fileId=file_id).execute()
        print(f"INFO: Successfully deleted file with ID: {file_id}")
        return {
            "status": "success",
            "message": f"File with ID '{file_id}' has been permanently deleted."
        }
    except Exception as e:
        print(f"ERROR: Failed to delete file with ID '{file_id}': {str(e)}")
        return {"status": "error", "message": f"Failed to delete file with ID '{file_id}': {str(e)}"}

delete_google_file_tool = FunctionTool(func=delete_google_file_by_id)