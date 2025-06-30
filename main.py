from flask import Flask, request, jsonify, redirect, url_for, send_from_directory
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from utils import create_message_with_attachment, replace_tags, random_us_name_file_ext
import os, json, time, threading, uuid

app = Flask(__name__)
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

pending_campaigns = {}
history_data = []

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/email_script.js')
def serve_js():
    return send_from_directory('.', 'email_script.js')

@app.route('/start-campaign', methods=['POST'])
def start_campaign():
    try:
        campaign_id = str(uuid.uuid4())
        emails_raw = request.form.get('emails', '').strip()
        subject_raw = request.form.get('subject', '').strip()
        body = request.form.get('body', '')
        client_secret_raw = request.form.get('clientSecret', '').strip()

        if not emails_raw or not client_secret_raw:
            return jsonify({"error": "Missing emails or Gmail client secret."}), 400

        try:
            client_secret = json.loads(client_secret_raw)
        except json.JSONDecodeError:
            return jsonify({"error": "Invalid JSON in Gmail client secret."}), 400

        emails = [e.strip() for e in emails_raw.splitlines() if e.strip()]
        subjects = [s.strip() for s in subject_raw.splitlines() if s.strip()]

        attachment_path = None
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename:
                filename = file.filename
                safe_filename = f"{uuid.uuid4().hex}_{filename}"
                attachment_path = os.path.join(UPLOAD_FOLDER, safe_filename)
                file.save(attachment_path)

        pending_campaigns[campaign_id] = {
            'emails': emails,
            'subject_lines': subjects,
            'body': body,
            'client_secret': client_secret,
            'attachment_path': attachment_path,
            'log': [],
            'progress': 0,
            'token': None,
            'stopped': False,
            'paused': False
        }

        flow = Flow.from_client_config(
            client_secret,
            scopes=SCOPES,
            redirect_uri='http://localhost:5000/oauth2callback'
        )
        auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline', state=campaign_id)

        return jsonify({"auth_url": auth_url, "campaign_id": campaign_id})

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route('/oauth2callback')
def oauth2callback():
    campaign_id = request.args.get('state')
    code = request.args.get('code')

    if not campaign_id or campaign_id not in pending_campaigns:
        return "Invalid or missing campaign ID (state)", 400

    try:
        client_secret = pending_campaigns[campaign_id]['client_secret']
        flow = Flow.from_client_config(client_secret, SCOPES, redirect_uri='http://localhost:5000/oauth2callback')
        flow.fetch_token(code=code)
        creds = flow.credentials

        pending_campaigns[campaign_id]['token'] = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }

        threading.Thread(target=email_sender_thread, args=(campaign_id,), daemon=True).start()

        return redirect(url_for('index') + f"#campaign={campaign_id}")
    except Exception as e:
        return f"OAuth callback error: {str(e)}", 500

def email_sender_thread(campaign_id):
    data = pending_campaigns[campaign_id]
    token_data = data['token']
    creds = Credentials(**token_data)
    service = build('gmail', 'v1', credentials=creds)

    for i, email in enumerate(data['emails']):
        if data['stopped']:
            data['log'].append("⛔ Sending stopped.")
            break

        while data['paused']:
            time.sleep(1)

        subject_template = data['subject_lines'][i % len(data['subject_lines'])] if data['subject_lines'] else "(No subject)"
        replaced_subject = replace_tags(subject_template, email)
        replaced_body = replace_tags(data['body'], email)

        if data['attachment_path']:
            ext = data['attachment_path'].split('.')[-1]
            renamed_attachment = random_us_name_file_ext(ext)
        else:
            renamed_attachment = None

        message = create_message_with_attachment(
            "me",
            email,
            replaced_subject,
            replaced_body,
            data['attachment_path'],
            renamed_attachment
        )

        try:
            service.users().messages().send(userId="me", body=message).execute()
            data['log'].append(f"✅ Sent to {email}")
            history_data.append({
                "email": email,
                "status": "Success",
                "subject": replaced_subject,
                "timestamp": time.time(),
                "campaign_id": campaign_id
            })
        except Exception as e:
            data['log'].append(f"❌ Failed to send to {email}: {str(e)}")
            history_data.append({
                "email": email,
                "status": "Fail",
                "subject": replaced_subject,
                "timestamp": time.time(),
                "campaign_id": campaign_id
            })

        data['progress'] += 1

        time.sleep(3)

    # Clean up uploaded attachment after sending all emails
    if data['attachment_path'] and os.path.exists(data['attachment_path']):
        os.remove(data['attachment_path'])

@app.route('/status/<campaign_id>')
def status(campaign_id):
    data = pending_campaigns.get(campaign_id)
    if not data:
        return jsonify({"error": "Campaign not found"}), 404
    return jsonify({
        "progress": data['progress'],
        "emails_count": len(data['emails']),
        "log": data['log'],
        "stopped": data['stopped'],
        "paused": data['paused']
    })

@app.route('/pause/<campaign_id>', methods=['POST'])
def pause(campaign_id):
    if campaign_id in pending_campaigns:
        pending_campaigns[campaign_id]['paused'] = True
        return '', 204
    return 'Not found', 404

@app.route('/resume/<campaign_id>', methods=['POST'])
def resume(campaign_id):
    if campaign_id in pending_campaigns:
        pending_campaigns[campaign_id]['paused'] = False
        return '', 204
    return 'Not found', 404

@app.route('/stop/<campaign_id>', methods=['POST'])
def stop(campaign_id):
    if campaign_id in pending_campaigns:
        pending_campaigns[campaign_id]['stopped'] = True
        return '', 204
    return 'Not found', 404

@app.route('/history.html')
def history_page():
    return send_from_directory('.', 'history.html')

@app.route('/history')
def get_history():
    return jsonify(history_data)

@app.route('/history/clear', methods=['POST'])
def clear_history():
    history_data.clear()
    return '', 204

if __name__ == '__main__':
    app.run(debug=True)
