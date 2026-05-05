import os
import json
import time
import subprocess
import csv

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

def wait_for_db():
    print("Waiting for DOMjudge API to be fully ready (this can take up to 2 minutes)...")
    for i in range(60):
        if os.path.exists('/opt/domjudge/domserver/webapp/bin/console'):
            try:
                # We try an API call to verify DB is actually migrated
                subprocess.run(['/opt/domjudge/domserver/webapp/bin/console', 'api:call', 'users'], check=True, capture_output=True)
                return True
            except subprocess.CalledProcessError:
                pass
        time.sleep(2)
            
    print("Error: Timed out waiting for DOMjudge to initialize.")
    return False

def set_system_passwords(admin_user, admin_pass, judge_pass):
    # Generate bcrypt hashes via PHP
    admin_hash = subprocess.check_output(['php', '-r', f'echo password_hash("{admin_pass}", PASSWORD_BCRYPT);']).decode('utf-8').strip()
    judge_hash = subprocess.check_output(['php', '-r', f'echo password_hash("{judge_pass}", PASSWORD_BCRYPT);']).decode('utf-8').strip()
    
    # Update directly in the database
    subprocess.run(['mysql', '-h', 'mariadb', '-u', 'root', '-prootpw', 'domjudge', '-e', f"UPDATE user SET password = '{admin_hash}' WHERE username = '{admin_user}';"], check=True)
    subprocess.run(['mysql', '-h', 'mariadb', '-u', 'root', '-prootpw', 'domjudge', '-e', f"UPDATE user SET password = '{judge_hash}' WHERE username = 'judgehost';"], check=True)
    print("System passwords updated successfully directly in the database.")

def main():
    if not wait_for_db():
        return

    admin_user = os.environ.get('ADMIN_USERNAME', 'admin')
    admin_pass = os.environ.get('ADMIN_PASSWORD', 'adminpassword')
    judge_pass = os.environ.get('JUDGEDAEMON_PASSWORD', 'judgehostpw')

    print("Setting system passwords...")
    try:
        set_system_passwords(admin_user, admin_pass, judge_pass)
    except Exception as e:
        print(f"Failed to set passwords: {e}")

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
                    "category": "Participants"
                })
                
                accounts.append({
                    "type": "team",
                    "name": team_name,
                    "username": username,
                    "password": password
                })

    if teams:
        print("Importing Teams...")
        try:
            res = api_call('users/teams', teams)
            print(f"Success for teams: {res}")
        except subprocess.CalledProcessError as e:
            print(f"Error importing teams: {e.stderr.strip()} {e.stdout.strip()}")
            
    if accounts:
        print("Importing Accounts...")
        try:
            res = api_call('users/accounts', accounts)
            print(f"Success for accounts: {res}")
        except subprocess.CalledProcessError as e:
            print(f"Error importing accounts: {e.stderr.strip()} {e.stdout.strip()}")
            
    print("Automated setup complete!")

if __name__ == "__main__":
    main()
