"""Optional Windows service. Installation is an explicit elevated desktop action."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import threading

NAME = 'LegalLibrary'


def service_data():
    return Path(os.environ.get('PROGRAMDATA', r'C:\ProgramData')) / 'LegalLibrary' / 'data'


def service_state():
    try:
        import win32serviceutil
        return win32serviceutil.QueryServiceStatus(NAME)[1]
    except Exception:
        return None


def dispatch():
    import servicemanager
    import win32service
    import win32serviceutil
    class LibraryService(win32serviceutil.ServiceFramework):
        _svc_name_ = NAME
        _svc_display_name_ = 'Legal Library'
        def __init__(self, args):
            super().__init__(args)
            self.stop_event = threading.Event()
        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING, waitHint=30000)
            self.stop_event.set()
        def SvcDoRun(self):
            from legal_platform.host import run_server
            run_server(service_data(), self.stop_event)
    servicemanager.Initialize()
    servicemanager.PrepareToHostSingle(LibraryService)
    servicemanager.StartServiceCtrlDispatcher()


def install(source_data, operator_sid):
    """Copy immutable program files to Program Files and grant only data access."""
    import win32service, win32serviceutil, win32security, ntsecuritycon
    from legal_platform.operations import installation_lock
    if not getattr(sys, 'frozen', False):
        raise RuntimeError('Use the packaged Windows application to install the service.')
    if service_state() is not None:
        raise RuntimeError('The service is already installed. Stop and remove it before upgrading.')
    source_data, target = Path(source_data).resolve(), service_data().resolve()
    program = Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'Legal Library'
    if program.exists():
        raise RuntimeError('The program installation folder already exists. Keep the existing installation or remove its old program files before reinstalling.')
    if target.exists() and any(target.iterdir()):
        raise RuntimeError('A service library already exists. Its data will not be overwritten. Use the installed data folder or restore into a new folder.')
    with installation_lock(source_data):
        # Ownership and a protected DACL prevent non-administrators modifying service code.
        program.mkdir(parents=True)
        acl = win32security.ACL()
        for sid, access in [(win32security.CreateWellKnownSid(win32security.WinBuiltinAdministratorsSid), ntsecuritycon.FILE_ALL_ACCESS),
                            (win32security.CreateWellKnownSid(win32security.WinLocalSystemSid), ntsecuritycon.FILE_ALL_ACCESS),
                            (win32security.CreateWellKnownSid(win32security.WinLocalServiceSid), ntsecuritycon.FILE_GENERIC_READ | ntsecuritycon.FILE_GENERIC_EXECUTE)]:
            acl.AddAccessAllowedAceEx(win32security.ACL_REVISION, 3, access, sid)
        win32security.SetNamedSecurityInfo(str(program), win32security.SE_FILE_OBJECT, win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION, None, None, acl, None)
        shutil.copytree(Path(sys.executable).parent, program, dirs_exist_ok=True)
        target.mkdir(parents=True, exist_ok=True)
        data_acl = win32security.ACL()
        for sid in (win32security.CreateWellKnownSid(win32security.WinBuiltinAdministratorsSid), win32security.CreateWellKnownSid(win32security.WinLocalSystemSid), win32security.CreateWellKnownSid(win32security.WinLocalServiceSid), win32security.ConvertStringSidToSid(operator_sid)):
            data_acl.AddAccessAllowedAceEx(win32security.ACL_REVISION, 3, ntsecuritycon.FILE_ALL_ACCESS, sid)
        win32security.SetNamedSecurityInfo(str(target), win32security.SE_FILE_OBJECT, win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION, None, None, data_acl, None)
        shutil.copytree(source_data, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.server.lock','.stop-request','logs'))
        win32serviceutil.InstallService('legal_platform.windows_service.LibraryService', NAME, 'Legal Library',
            startType=win32service.SERVICE_AUTO_START, userName=r'NT AUTHORITY\LocalService',
            exeName=str(program / Path(sys.executable).name), exeArgs='--service-dispatch',
            description='Shared document library and source-based research on your local network.', delayedstart=True)
        win32serviceutil.StartService(NAME)


def manage(action):
    import win32serviceutil
    if action == 'start':
        win32serviceutil.StartService(NAME)
    elif action == 'stop':
        win32serviceutil.StopService(NAME)
        win32serviceutil.WaitForServiceStatus(NAME, 1, 30)
    elif action == 'remove':
        if service_state() != 1:
            manage('stop')
        win32serviceutil.RemoveService(NAME)
        # Documents and application files are intentionally retained for recovery.
    else:
        raise ValueError('Unknown service operation')


def allow_private_lan(port):
    """Explicit opt-in: Private profile and local subnet only, never public Internet."""
    port = int(port)
    if not 1024 <= port <= 65535:
        raise ValueError('Invalid port')
    subprocess.run(['netsh', 'advfirewall', 'firewall', 'add', 'rule', 'name=Legal Library LAN',
        'dir=in', 'action=allow', 'protocol=TCP', f'localport={port}', 'profile=private', 'remoteip=localsubnet'], check=True, creationflags=0x08000000)
