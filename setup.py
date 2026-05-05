import os
import json
import time
import subprocess
import csv
import zipfile

def wait_for_api():
    print("Waiting for DOMjudge API to be fully ready (this can take up to 2 minutes)...")
    for i in range(60):
        if os.path.exists('/opt/domjudge/domserver/webapp/bin/console'):
            try:
                subprocess.run(['/opt/domjudge/domserver/webapp/bin/console', 'api:call', 'users'], check=True, capture_output=True)
                return True
            except subprocess.CalledProcessError:
                pass
        time.sleep(2)
            
    print("Error: Timed out waiting for DOMjudge to initialize.")
    return False

def api_call(endpoint, json_data):
    tmp_file = f'/tmp/{endpoint.replace("/", "_")}.json'
    with open(tmp_file, 'w') as f:
        json.dump(json_data, f)
    
    cmd = [
        '/opt/domjudge/domserver/webapp/bin/console',
        'api:call', '-m', 'POST', f'-fjson={tmp_file}', endpoint
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout.strip()

def api_upload_problem(zip_path, problem_id):
    cmd = [
        '/opt/domjudge/domserver/webapp/bin/console',
        'api:call', '-m', 'POST', f'-fzip={zip_path}', '-d', f'problem={problem_id}', 'problems'
    ]
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout.strip()

def zip_problem_directory(pdir, zip_path):
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(pdir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, pdir)
                zf.write(file_path, arcname)

def set_system_passwords(admin_user, admin_pass, judge_pass):
    admin_hash = subprocess.check_output(['php', '-r', f'echo password_hash("{admin_pass}", PASSWORD_BCRYPT);']).decode('utf-8').strip()
    judge_hash = subprocess.check_output(['php', '-r', f'echo password_hash("{judge_pass}", PASSWORD_BCRYPT);']).decode('utf-8').strip()
    
    subprocess.run(['mysql', '-h', 'mariadb', '-u', 'root', '-prootpw', 'domjudge', '-e', f"UPDATE user SET password = '{admin_hash}' WHERE username = '{admin_user}';"], check=True)
    subprocess.run(['mysql', '-h', 'mariadb', '-u', 'root', '-prootpw', 'domjudge', '-e', f"UPDATE user SET password = '{judge_hash}' WHERE username = 'judgehost';"], check=True)
    print("System passwords updated successfully.")

def main():
    if not wait_for_api():
        return

    admin_user = os.environ.get('ADMIN_USERNAME', 'admin')
    admin_pass = os.environ.get('ADMIN_PASSWORD', 'adminpassword')
    judge_pass = os.environ.get('JUDGEDAEMON_PASSWORD', 'judgehostpw')

    print("Setting system passwords...")
    set_system_passwords(admin_user, admin_pass, judge_pass)

    groups = [{"id": "participants", "name": "Participants", "visible": True}]
    teams = []
    accounts = []
    
    if os.path.exists('/teams.csv'):
        with open('/teams.csv', 'r') as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or row[0].startswith('#'):
                    continue
                team_name, username, password = row[0], row[1], row[2]
                
                teams.append({
                    "id": username,
                    "name": team_name,
                    "group_ids": ["participants"]
                })
                
                accounts.append({
                    "type": "team",
                    "username": username,
                    "password": password,
                    "team_id": username
                })

    if groups:
        print("Importing Groups via API...")
        try:
            res = api_call('users/groups', groups)
            print(f"Success for groups: {res}")
        except subprocess.CalledProcessError as e:
            print(f"Error importing groups: {e.stderr.strip() if e.stderr else e.stdout.strip()}")

    if teams:
        print("Importing Teams via API...")
        try:
            res = api_call('users/teams', teams)
            print(f"Success for teams: {res}")
        except subprocess.CalledProcessError as e:
            print(f"Error importing teams: {e.stderr.strip() if e.stderr else e.stdout.strip()}")
            
    if accounts:
        print("Importing Accounts via API...")
        try:
            res = api_call('users/accounts', accounts)
            print(f"Success for accounts: {res}")
        except subprocess.CalledProcessError as e:
            print(f"Error importing accounts: {e.stderr.strip() if e.stderr else e.stdout.strip()}")
            
    print("Checking for problem directories to upload...")
    if os.path.exists('/problems'):
        for entry in os.listdir('/problems'):
            pdir = os.path.join('/problems', entry)
            if os.path.isdir(pdir):
                print(f"Zipping and uploading problem '{entry}'...")
                zip_path = f'/tmp/{entry}.zip'
                zip_problem_directory(pdir, zip_path)
                try:
                    res = api_upload_problem(zip_path, entry)
                    print(f"Success for {entry}: {res}")
                except subprocess.CalledProcessError as e:
                    print(f"Error uploading {entry}: {e.stderr.strip() if e.stderr else e.stdout.strip()}")

    print("Automated setup complete!")

if __name__ == "__main__":
    main()
