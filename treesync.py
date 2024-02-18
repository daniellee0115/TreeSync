import os
import json
import base64
import time
import subprocess
from llm import llmCall
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from flask import Flask, request

base_dir = os.path.dirname(__file__)
prev_startHistoryId = None
prev_email_ids = {}
prev_events = {}
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/calendar']

def get_gmail_service():
    """Authenticate and create a Gmail service."""
    # Load credentials from a JSON file or perform OAuth2 authentication
    creds = None
    if os.path.exists(os.path.join(base_dir, 'token.json')):
        creds = Credentials.from_authorized_user_file(os.path.join(base_dir,'token.json'))
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                os.path.join(base_dir, 'credentials.json'), SCOPES)
            creds = flow.run_local_server(port=0)
        # Save credentials for future use
        with open(os.path.join(base_dir, 'token.json'), 'w') as token:
            token.write(creds.to_json())

    # Create Gmail service
    service = build('gmail', 'v1', credentials=creds)
    return service

def get_calendar_service():
    """Authenticate and create a Google Calendar service."""
    creds = None
    if os.path.exists(os.path.join(base_dir, 'token.json')):
        creds = Credentials.from_authorized_user_file(os.path.join(base_dir,'token.json'))
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                os.path.join(base_dir, 'credentials.json'), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(os.path.join(base_dir, 'token.json'), 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)
    return service

def get_latest_email(service, startHistoryId):
    """Fetch the latest email from Gmail."""
    # Get the list of messages
    results = service.users().messages().list(userId='me', labelIds=['INBOX']).execute()
    messages = results.get('messages', [])

    if not messages:
        print("No messages found.")
        return []
    new_email_ids = set()
    if startHistoryId is None:
        # Get the ID of the latest message
        new_email_ids.add(messages[0]['id'])
    else:
        # Gets email ids of all emails after push notification
        response = service.users().history().list(userId='me', startHistoryId=startHistoryId).execute()
        changes = response.get('history', [])
        new_email_ids = set()
        for change in changes:
            for message_change in change.get('messages', []):
                message_id = message_change['id']
                if message_id not in prev_email_ids:
                    prev_email_ids[message_id] = 1
                    new_email_ids.add(message_id)

    # Retrieve the latest messages
    new_email_ids = list(new_email_ids)
    prev_startHistoryId = new_email_ids[0]
    messages = [service.users().messages().get(userId='me', id=message_id).execute() for message_id in new_email_ids]
    return messages

def return_email_content(message):
    """Print the contents of the email."""
    # Date of email
    date = llmCall(["You are an agent that receives a string with a date and time, along with other information. Your job is to return the date (year, month, day, name of day (Ex. Thursday, Friday, Saturday, etc.)) and time (hour and minutes in a 24-hour military time system, where you convert AM/PM to the correct hour count). Do not output any filler words or extra words or extra spaces or indents that is not the answer. Make sure to put the answer in one line. Make sure that the answer has no unnecessary space in the front or in the back. Ex: Friday, January 1, 2023 18:00:00", message['payload']['headers'][1]['value']])
    payload = message['payload']
    parts = payload.get('parts', [payload])
    for part in parts:
        if part['mimeType'] == 'text/plain' or part['mimeType'] == 'text/html':
            data = part['body']['data']
            time.sleep(1)
            # Body of email
            body = llmCall(["You are an agent that receives an html code which contains a text body. Your job is to return the text body only. Do not return anything else.", base64.urlsafe_b64decode(data).decode('utf-8')[:3000]])
            break
    headers = payload.get('headers', [])
    for header in headers:
        if header['name'].lower() == 'subject':
            subject = header['value']
            break
    return date, subject, body

def determine_event_importance(email_subject, email_body):
        importance_prompt = f"""

        You are an agent that receives an email event with a subject and body. Your task is to assess the importance level of the event based on the provided information.

        Consider the following factors when assessing importance:
        - Capitalization: Words in all caps or with excessive capitalization may indicate urgency.
        - Specific keywords: Look for words like 'urgent', 'important', 'deadline', 'action required', etc.
        - Tone: Evaluate the overall tone of the email. Does it convey a sense of urgency or importance?
        - Timing: Is there a specific deadline or time-sensitive information mentioned?

        Based on these considerations, classify the event as one of the following:
        1. 'Very important': The email contains critical information that requires immediate attention or action. Or if the event is taking place very soon from when the email was received.
        2. 'Important': The email is significant and should be addressed promptly.
        3. 'Less important': The email is informational or non-urgent.

        Provide the corresponding number (1, 2, or 3) to indicate the importance level of the email event.
        """

        importance_level = llmCall([importance_prompt, f"this is the email body: {email_body} and this is the email subject: {email_subject}"])

        print("importance level determined to be:", importance_level)

        # Map the LLM's response to your color codes
        if importance_level:
            if "1" in importance_level:
                return "11"  # Dark red
            elif "2" in importance_level:
                return "6"   # Light red
            elif "3" in importance_level:
                return "5"   # Yellow
        return "8" # Unidentified

def create_event(service, event):
    """Create a new event in the user's calendar."""
    event = json.loads(event)
    event = service.events().insert(calendarId='primary', body=event).execute()
    print('Event created:', event.get('htmlLink'))

app = Flask(__name__)
process = subprocess.Popen("/opt/homebrew/Caskroom/ngrok/3.6.0/ngrok http --domain=lucky-frankly-cougar.ngrok-free.app 127.0.0.1:5000", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
email_service = get_gmail_service()
calendar_service = get_calendar_service()
@app.route('/', methods=['POST'])
def endpoint_handler():
    if request.method == 'POST':
        latest_emails = get_latest_email(email_service, prev_startHistoryId)
        for id in latest_emails:
            email_date, email_subject, email_body = return_email_content(id)
            color_id = determine_event_importance(email_subject, email_body)
            sample_event = """{"summary": "Google I/O 2015",
            "description": "A chance to hear more about Google\'s developer products.",
            "start": {
                    "dateTime": "2015-05-28T09:00:00-08:00",
                    "timeZone": "America/Los_Angeles"},
            "end": {
                    "dateTime": "2015-05-28T17:00:00-08:00",
                    "timeZone": "America/Los_Angeles"},
            "colorId": 6
                }"""
            event_present = llmCall([f"""You are an agent that receives an email subject and its body, along with the current date and time. Your job is to figure out if the email contains an event scheduled in the future. For example, if the email asks the recepient if he wants to grab lunch tomorrow, the email contains an event scheduled in the future or in the present. If the email is telling the recepient about a news event that happened yesterday, the email does not contain an event scheduled in the future or in the present. Your job is to return either 1 or 0 depending on this problem. Output 1 if the email contains an event scheduled in the future or in the present. Output 0 if the email does not contain an event scheduled in the future or in the present. Only output either 1 or 0. Do not output anything else and do not explain your answer.""", f"""Here is the email subject: {email_subject}, here is the email body: {email_body}, here is the current date and time: {email_date}"""])
            print(event_present)
            if event_present is not None and '1' in event_present:
                print(email_body, email_subject, email_date)
                scheduled_event = llmCall([f"""You are an agent that receives an email about an event and also receives current date and time. You should create an object with a summary, description, start time, and end time (all time output should be in 24-hour military time system), using the current date and time as well as the date and time mentioned in the email body. Only output the answer. Do not output any filler words or extra words or extra spaces or indents that is not the answer. Make sure that the answer has no unnecessary space in the front or in the back. Be specific with the event summary and description. Include any relevant details in the email. Make sure that the answer follows this sample format, where the -08:00 is the time zone for PST: {sample_event}""", f"""Current date and time: {email_date}, email body: {email_body}, email subject: {email_subject}, color id: {color_id}. Do not output anything else other than the information between the brackets."""])
                print(scheduled_event)
                while scheduled_event is None:
                    scheduled_event = llmCall([f"""You are an agent that receives an email about an event and also receives current date and time. You should create an object with a summary, description, start time, and end time (all time output should be in 24-hour military time system), using the current date and time as well as the date and time mentioned in the email body. Only output the answer. Do not output any filler words or extra words or extra spaces or indents that is not the answer. Make sure that the answer has no unnecessary space in the front or in the back. Be specific with the event summary and description. Include any relevant details in the email. Make sure that the answer follows this sample format, where the -08:00 is the time zone for PST: {sample_event}""", f"""Current date and time: {email_date}, email body: {email_body}, email subject: {email_subject}, color id: {color_id}. Do not output anything else other than the information between the brackets."""])
                if scheduled_event not in prev_events:
                    prev_events[str(scheduled_event)] = 1
                    create_event(calendar_service, scheduled_event)
        return 'POST request received', 200
    else:
        return 'Only POST requests are allowed', 405
    
if __name__ == '__main__':
    app.run()