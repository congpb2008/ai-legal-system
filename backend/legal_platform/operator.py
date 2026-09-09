"""Host-only maintenance commands for source and Docker installations.

Passphrases are prompted privately, never accepted as command-line arguments.
The same operations power the Windows launcher. No web endpoint invokes this.
"""
import argparse
from getpass import getpass
from legal_platform.paths import data_root


def main(argv=None):
    parser = argparse.ArgumentParser(description='Legal Library host maintenance')
    parser.add_argument('--data-dir', default=str(data_root()), help='Library data folder')
    commands = parser.add_subparsers(dest='operation', required=True)
    commands.add_parser('backup', help='Create an encrypted backup').add_argument('destination')
    restore_parser = commands.add_parser('restore', help='Restore into a new, empty folder')
    restore_parser.add_argument('archive')
    restore_parser.add_argument('destination')
    commands.add_parser('recover-admin', help='Recover an existing active administrator while stopped').add_argument('username')
    args = parser.parse_args(argv)
    from legal_platform.operations import backup, restore, recover_administrator
    try:
        if args.operation == 'restore':
            password = getpass('Backup passphrase: ')
            result = restore(args.archive, args.destination, password)
            print(f'Restored to {result}. Start that library and sign in again.')
            return
        prompt = 'New administrator password' if args.operation == 'recover-admin' else 'Backup passphrase'
        password = getpass(prompt + ' (at least 12 characters): ')
        if password != getpass('Confirm: '):
            raise ValueError('Passphrases do not match.')
        if args.operation == 'backup':
            result = backup(args.data_dir, args.destination, password)
            print(f'Encrypted backup saved to {result}. Keep a separate copy and its passphrase.')
        else:
            username = recover_administrator(args.data_dir, args.username, password)
            print(f'Administrator {username} recovered. Start the server and sign in again.')
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
