import shutil
import os
import datetime

def backup_project():
    from kr_etf_investor.flask_app import VERSION
    project_dir = os.getcwd()
    # Convention: kr_etf_investor_backup_vX.X.X_YYYYMMDD_HHMM
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    backup_dir_name = f"kr_etf_investor_backup_v{VERSION}_{timestamp}"
    backup_root = os.path.join(project_dir, "backups")
    dest_dir = os.path.join(backup_root, backup_dir_name)

    if not os.path.exists(backup_root):
        os.makedirs(backup_root)

    print(f"Backing up project to: {dest_dir}")

    # Ignore patterns
    def ignore_patterns(path, names):
        ignored = []
        for name in names:
            if name in ['backups', '.git', '__pycache__', 'venv', '.idea', '.vscode', 'node_modules']:
                ignored.append(name)
            elif name.endswith('.pyc'):
                ignored.append(name)
        return ignored

    try:
        shutil.copytree(project_dir, dest_dir, ignore=ignore_patterns)
        print("Backup completed successfully!")
    except Exception as e:
        print(f"Backup failed: {e}")

if __name__ == "__main__":
    backup_project()
