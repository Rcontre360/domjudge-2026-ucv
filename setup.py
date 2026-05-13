import os
import subprocess
import time


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


def set_system_passwords(admin_user, admin_pass, judge_pass):
    admin_hash = subprocess.check_output(['php', '-r', f'echo password_hash("{admin_pass}", PASSWORD_BCRYPT);']).decode('utf-8').strip()
    judge_hash = subprocess.check_output(['php', '-r', f'echo password_hash("{judge_pass}", PASSWORD_BCRYPT);']).decode('utf-8').strip()

    subprocess.run(['mysql', '-h', 'mariadb', '-u', 'root', '-prootpw', 'domjudge', '-e', f"UPDATE user SET password = '{admin_hash}' WHERE username = '{admin_user}';"], check=True)
    subprocess.run(['mysql', '-h', 'mariadb', '-u', 'root', '-prootpw', 'domjudge', '-e', f"UPDATE user SET password = '{judge_hash}' WHERE username = 'judgehost';"], check=True)
    print("System passwords updated successfully.")


def configure_languages():
    """Enable only C, C++, and Python 3 (PyPy3); disable everything else."""
    allowed = "'c','cpp','py3'"
    subprocess.run([
        'mysql', '-h', 'mariadb', '-u', 'root', '-prootpw', 'domjudge', '-e',
        f"UPDATE language SET allow_submit = (langid IN ({allowed}));",
    ], check=True)
    print(f"Enabled languages: {allowed}; all others disabled.")


def main():
    if not wait_for_api():
        return

    admin_user = os.environ.get('ADMIN_USERNAME', 'admin')
    admin_pass = os.environ.get('ADMIN_PASSWORD', 'adminpassword')
    judge_pass = os.environ.get('JUDGEDAEMON_PASSWORD', 'judgehostpw')

    print("Setting system passwords...")
    set_system_passwords(admin_user, admin_pass, judge_pass)

    print("Configuring languages...")
    configure_languages()

    print("Automated setup complete!")


if __name__ == "__main__":
    main()
