def calendar(event):
    import os
    import json
    from llm import llmCall
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from datetime import datetime, timedelta

    # Define the scopes required for accessing Google Calendar
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 'https://www.googleapis.com/auth/calendar']

    def authenticate():
        """Authenticate and create a Google Calendar service."""
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
            with open('token.json', 'w') as token:
                token.write(creds.to_json())

        service = build('calendar', 'v3', credentials=creds)
        return service

    def create_event(service, event):
        """Create a new event in the user's calendar."""
        event = json.loads(event)

        event = service.events().insert(calendarId='primary', body=event).execute()
        print('Event created:', event.get('htmlLink'))

    service = authenticate()
    create_event(service, event)