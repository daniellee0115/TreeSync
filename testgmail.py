def gmail():
    import os
    import base64
    import time
    from llm import llmCall
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    # Define the scopes required for accessing Gmail
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/calendar']

    def get_gmail_service():
        """Authenticate and create a Gmail service."""
        # Load credentials from a JSON file or perform OAuth2 authentication
        creds = None
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json')
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            # Save credentials for future use
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        # Create Gmail service
        service = build('gmail', 'v1', credentials=creds)
        return service

    def get_latest_email(service):
        """Fetch the latest email from Gmail."""
        # Get the list of messages
        results = service.users().messages().list(userId='me', labelIds=['INBOX']).execute()
        #print(results)
        messages = results.get('messages', [])

        if not messages:
            print("No messages found.")
            return

        # Get the ID of the latest message
        latest_message_id = messages[1]['id']

        # Retrieve the latest message
        message = service.users().messages().get(userId='me', id=latest_message_id).execute()
        #print(message)
        return message

    def return_email_content(message):
        """Print the contents of the email."""
        # Date of email
        date = llmCall(["You are an agent that receives a string with a date and time, along with other information. Your job is to return the date (year, month, day, name of day (Ex. Friday)) and time (hour and minutes with AM/PM included). Do not output any filler words or extra words or extra spaces or indents that is not the answer. Make sure to put the answer in one line. Make sure that the answer has no unnecessary space in the front or in the back.", message['payload']['headers'][1]['value']])
        payload = message['payload']
        parts = payload.get('parts', [payload])
        for part in parts:
            if part['mimeType'] == 'text/plain' or part['mimeType'] == 'text/html':
                data = part['body']['data']
                # Decode the email body
                time.sleep(1)
                # Body of email
                body = llmCall(["You are an agent that receives an html code which contains a text body. Your job is to return the text body only. Do not return anything else.", base64.urlsafe_b64decode(data).decode('utf-8')[:3000]])
        return date, body

    # Authenticate and create Gmail service
    service = get_gmail_service()

    # Get the latest email
    latest_email = get_latest_email(service)
    if latest_email:
        email_date, email_body = return_email_content(latest_email)
        #print(email_date)
        sample_event = """{"summary": "Google I/O 2015",
        "description": "A chance to hear more about Google\'s developer products.",
        "start": {
                "dateTime": "2015-05-28T09:00:00-07:00",
                "timeZone": "America/Los_Angeles"},
        "end": {
                "dateTime": "2015-05-28T17:00:00-07:00",
                "timeZone": "America/Los_Angeles"}
            }"""
        scheduled_event = llmCall([f"""You are an agent that receives an email about an event and also receives current date and time. You should create an object with a summary, description, start time, and end time. Only output the answer. Do not output any filler words or extra words or extra spaces or indents that is not the answer. Make sure that the answer has no unnecessary space in the front or in the back. Be specific with the event summary and description. Include any relevant details in the email. Make sure that the answer follows this sample format: {sample_event}""", f"""Current date and time: {email_date}, email body: {email_body}. Do not output anything else other than the information between the brackets."""])
        print(scheduled_event)
        return scheduled_event