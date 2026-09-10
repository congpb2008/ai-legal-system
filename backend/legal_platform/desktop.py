"""A small Windows control panel; the product itself runs in any LAN browser."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import webbrowser
from legal_platform.paths import data_root


def launch(*, self_check=False):
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog, simpledialog
    from legal_platform.host import addresses, load_settings, save_settings, ensure_certificate, running_host, stop_host
    from legal_platform.operations import installation_in_use
    from legal_platform.windows_service import service_data, service_state
    from legal_platform.desktop_language import VI
    preferences = data_root().parent / 'launcher-preferences.json'
    try:
        language = json.loads(preferences.read_text(encoding='utf-8')).get('language', 'vi')
    except (OSError, ValueError, TypeError, AttributeError):
        language = 'vi'
    language = 'en' if language == 'en' else 'vi'
    def t(text): return VI.get(text, text) if language == 'vi' else text
    root = tk.Tk()
    root.title(t('Legal Library Server'))
    root.geometry(f'780x{min(740, max(500, root.winfo_screenheight() - 100))}')
    root.minsize(710, 500)
    if self_check:
        root.withdraw()
    root.configure(bg='#f6f5ef')
    style = ttk.Style()
    style.theme_use('clam')
    style.configure('TFrame', background='#f6f5ef')
    style.configure('TLabel', background='#f6f5ef', font=('Segoe UI', 10))
    style.configure('TButton', font=('Segoe UI', 10), padding=8)
    preferences = data_root().parent / 'launcher-preferences.json'
    preferred = data_root()
    try:
        saved = json.loads(preferences.read_text(encoding='utf-8'))
        if Path(saved['data_dir']).is_dir():
            preferred = Path(saved['data_dir'])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    directory = tk.StringVar(value=str(service_data() if service_state() is not None else preferred))
    port, tls = tk.StringVar(), tk.BooleanVar()
    status, urls, setup = tk.StringVar(value=t('Stopped')), tk.StringVar(), tk.StringVar()
    running = {'process': None}
    canvas = tk.Canvas(root, background='#f6f5ef', highlightthickness=0)
    scrollbar = ttk.Scrollbar(root, orient='vertical', command=canvas.yview)
    scrollbar.pack(side='right', fill='y')
    canvas.pack(side='left', fill='both', expand=True)
    canvas.configure(yscrollcommand=scrollbar.set)
    frame = ttk.Frame(canvas, padding=24)
    frame_window = canvas.create_window((0, 0), window=frame, anchor='nw')
    frame.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>', lambda event: canvas.itemconfigure(frame_window, width=event.width))
    root.bind('<MouseWheel>', lambda event: canvas.yview_scroll(-int(event.delta / 120), 'units'))
    language_row=ttk.Frame(frame);language_row.pack(fill='x',pady=(0,10))
    ttk.Label(language_row,text='Ngôn ngữ / Language').pack(side='left')
    language_choice=ttk.Combobox(language_row,values=['Tiếng Việt','English'],state='readonly',width=15)
    language_choice.set('English' if language=='en' else 'Tiếng Việt')
    language_choice.pack(side='right')
    def change_language(_event):
        nonlocal language
        next_language='en' if language_choice.get()=='English' else 'vi'
        try:
            try: saved_preferences=json.loads(preferences.read_text(encoding='utf-8'))
            except (OSError, ValueError): saved_preferences={}
            if not isinstance(saved_preferences,dict): saved_preferences={}
            saved_preferences['language']=next_language
            preferences.parent.mkdir(parents=True,exist_ok=True)
            preferences.write_text(json.dumps(saved_preferences),encoding='utf-8')
        except OSError as exc:
            language_choice.set('English' if language=='en' else 'Tiếng Việt')
            messagebox.showerror(t('Could not complete action'),str(exc),parent=root);return
        reverse={translated:original for original,translated in VI.items()}
        language=next_language
        def update(widget):
            try:
                text=widget.cget('text');widget.configure(text=t(reverse.get(text,text)))
            except tk.TclError: pass
            for child in widget.winfo_children(): update(child)
        update(frame);root.title(t('Legal Library Server'));refresh()
    language_choice.bind('<<ComboboxSelected>>',change_language)
    ttk.Label(frame, text=t('§  Legal Library Server'), font=('Segoe UI', 24, 'bold')).pack(anchor='w')
    ttk.Label(frame, text=t('Keep this machine on. Colleagues use the library in their web browser.'), wraplength=670).pack(anchor='w', pady=(6,18))
    ttk.Label(frame, text=t('Library data folder')).pack(anchor='w')
    line = ttk.Frame(frame); line.pack(fill='x')
    folder_entry = ttk.Entry(line, textvariable=directory); folder_entry.pack(side='left', fill='x', expand=True)
    def error(fn):
        def wrapped():
            try: fn()
            except Exception as exc: messagebox.showerror(t('Could not complete action'), str(exc), parent=root)
        return wrapped
    def load():
        settings = load_settings(directory.get())
        port.set(str(settings['port'])); tls.set(settings['https'])
        refresh()
    def choose():
        value = filedialog.askdirectory(parent=root, title=t('Choose the library data folder'))
        if value: directory.set(value); load()
    browse_button = ttk.Button(line, text=t('Browse…'), command=error(choose))
    browse_button.pack(side='left', padx=(8,0))
    line = ttk.Frame(frame); line.pack(fill='x', pady=12)
    ttk.Label(line, text=t('Port')).pack(side='left')
    port_entry = ttk.Entry(line, textvariable=port, width=8)
    port_entry.pack(side='left', padx=10)
    tls_button = ttk.Checkbutton(line, text=t('Use HTTPS (recommended)'), variable=tls)
    tls_button.pack(side='left')
    ttk.Label(frame, textvariable=status, font=('Segoe UI', 12, 'bold')).pack(anchor='w', pady=8)
    def save():
        save_settings(directory.get(), {'host':'0.0.0.0','port':int(port.get()),'https':tls.get()})
        preferences.parent.mkdir(parents=True, exist_ok=True)
        preferences.write_text(json.dumps({'data_dir': str(Path(directory.get()).resolve()), 'language': language}), encoding='utf-8')
    def elevate(args):
        if not getattr(sys,'frozen',False):
            raise ValueError(t('Use the Windows executable for service and firewall controls.'))
        import ctypes
        result = ctypes.windll.shell32.ShellExecuteW(None, 'runas', sys.executable, subprocess.list2cmdline(args), None, 0)
        if result <= 32: raise RuntimeError(t('Windows administrator approval was not granted.'))
    def start():
        if service_state() is not None and Path(directory.get()).resolve()==service_data().resolve():
            if service_state() != 1:
                return
            save()
            elevate(['--service-action','start']); return
        if installation_in_use(directory.get()):
            if not running_host(directory.get()):
                raise ValueError(t('This folder is in use by another server. Stop it from the place where it was started.'))
            refresh()
            return
        save()
        command = [sys.executable] if getattr(sys,'frozen',False) else [sys.executable,'-m','legal_platform.desktop']
        running['process'] = subprocess.Popen(command+['--serve','--data-dir',directory.get()], creationflags=0x08000000 if os.name=='nt' else 0)
        folder_entry.configure(state='disabled')
        status.set(t('Starting…'))
    def stop():
        if service_state() is not None and Path(directory.get()).resolve()==service_data().resolve():
            elevate(['--service-action','stop']); return
        stop_host(directory.get())
        status.set(t('Stopping after current work…'))
    def url(): return ('https' if tls.get() else 'http')+'://localhost:'+port.get()
    def open_library(): webbrowser.open(url())
    line=ttk.Frame(frame);line.pack(fill='x')
    for title, fn in [(t('Start server'),start),(t('Stop server'),stop),(t('Open library'),open_library)]:
        ttk.Button(line,text=title,command=error(fn)).pack(side='left',padx=(0,8))
    ttk.Label(frame, text=t('Addresses to share on this LAN'), font=('Segoe UI', 11, 'bold')).pack(anchor='w',pady=(18,4))
    ttk.Entry(frame,textvariable=urls,state='readonly').pack(fill='x')
    ttk.Label(frame, text=t('First administrator setup code (available after starting)'), font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(14,4))
    ttk.Entry(frame,textvariable=setup,state='readonly').pack(fill='x')
    ttk.Label(frame, text=t('On first use, open the library and create your administrator account with this code.'),wraplength=680).pack(anchor='w',pady=(4,10))
    def certificate():
        cert,key=ensure_certificate(directory.get())
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes
        fingerprint=x509.load_pem_x509_certificate(cert.read_bytes()).fingerprint(hashes.SHA256()).hex(':')
        destination=filedialog.asksaveasfilename(parent=root,title=t('Export public HTTPS certificate'),defaultextension='.crt',initialfile='Legal-Library.crt')
        if destination: Path(destination).write_bytes(cert.read_bytes())
        messagebox.showinfo(t('HTTPS certificate'), t('This installation uses its own certificate. Ask your IT administrator to trust the exported public certificate on LAN browsers, or replace tls/server.crt and tls/server.key with your organization’s certificate.\n\nDo not share server.key.\n\nSHA-256 fingerprint:\n')+fingerprint, parent=root)
    def firewall():
        if messagebox.askyesno(t('Allow access on your LAN?'), t('Add a Windows Firewall rule for this port on Private networks, restricted to the local subnet? Windows will ask for administrator approval.'),parent=root):
            elevate(['--allow-lan',port.get()])
    def install():
        if installation_in_use(directory.get()):
            raise ValueError(t('Stop the server and wait for “Stopped” before installing the service.'))
        save()
        if not messagebox.askyesno(t('Run automatically after restart?'), t('Install the application in Program Files, copy this library to ProgramData, and start it as a Windows service? The current data copy is kept. Windows will ask for administrator approval.'),parent=root): return
        import win32api,win32security
        token=win32security.OpenProcessToken(win32api.GetCurrentProcess(),win32security.TOKEN_QUERY)
        sid=win32security.ConvertSidToStringSid(win32security.GetTokenInformation(token,win32security.TokenUser)[0])
        elevate(['--install-service','--data-dir',directory.get(),'--operator-sid',sid])
    line=ttk.Frame(frame);line.pack(fill='x',pady=6)
    for title, fn in [(t('HTTPS certificate…'),certificate),(t('Allow LAN access…'),firewall),(t('Install as service…'),install)]:
        ttk.Button(line,text=title,command=error(fn)).pack(side='left',padx=(0,8))
    def backup():
        from legal_platform.operations import backup as do_backup
        destination=filedialog.asksaveasfilename(parent=root,title=t('Save encrypted backup'),defaultextension='.legalbackup',initialfile='Legal-Library.legalbackup')
        if not destination:return
        password=simpledialog.askstring(t('Protect backup'),t('Backup passphrase (at least 12 characters). Keep it somewhere safe; it cannot be recovered.'),show='*',parent=root)
        if password is None:return
        confirm=simpledialog.askstring(t('Confirm passphrase'),t('Enter the backup passphrase again.'),show='*',parent=root)
        if password!=confirm:raise ValueError(t('Passphrases do not match.'))
        status.set(t('Creating encrypted backup…'))
        task(lambda:do_backup(directory.get(),destination,password),t('Encrypted backup saved.'))
    def restore():
        from legal_platform.operations import restore as do_restore
        archive=filedialog.askopenfilename(parent=root,title=t('Choose encrypted backup'),filetypes=[(t('Legal Library backup'),'*.legalbackup')])
        if not archive:return
        destination=filedialog.askdirectory(parent=root,title=t('Choose an EMPTY folder to restore into'))
        if not destination:return
        password=simpledialog.askstring(t('Unlock backup'),t('Backup passphrase'),show='*',parent=root)
        if password is None:return
        task(lambda:do_restore(archive,destination,password),t('Backup restored. Browse to the restored data folder, then start the server. All users must sign in again.'))
    def task(fn,message):
        def worker():
            try:
                fn();root.after(0,lambda:messagebox.showinfo(t('Completed'),message,parent=root))
            except Exception as exc:
                text=str(exc);root.after(0,lambda:messagebox.showerror(t('Action failed'),text,parent=root))
        threading.Thread(target=worker,daemon=True).start()
    line=ttk.Frame(frame);line.pack(fill='x',pady=6)
    for title, fn in [(t('Back up library…'),backup),(t('Restore backup…'),restore),(t('Open data folder'),lambda:os.startfile(directory.get()))]:
        ttk.Button(line,text=title,command=error(fn)).pack(side='left',padx=(0,8))
    def remove():
        if messagebox.askyesno(t('Remove automatic service?'), t('Stop and unregister the Windows service? Documents and program files will be kept.'),parent=root):elevate(['--service-action','remove'])
    def recover_admin():
        if installation_in_use(directory.get()):
            raise ValueError(t('Stop the server before recovering an administrator account.'))
        if not messagebox.askyesno(t('Recover an administrator account?'),
                t('Use this only on the host when administrators cannot sign in. It resets an existing active administrator’s password, signs out that account’s devices and records the recovery in the audit log. It cannot create or promote an account.'), parent=root):
            return
        username = simpledialog.askstring(t('Administrator username'), t('Existing administrator username:'), parent=root)
        if not username:
            return
        password = simpledialog.askstring(t('New password'), t('New password (12–256 characters):'), show='*', parent=root)
        if password is None:
            return
        confirm = simpledialog.askstring(t('Confirm password'), t('Enter the new password again:'), show='*', parent=root)
        if password != confirm:
            raise ValueError(t('Passwords do not match.'))
        from legal_platform.operations import recover_administrator
        task(lambda: recover_administrator(directory.get(), username, password),
             t('Administrator recovered. Start the server and sign in with the new password.'))
    line = ttk.Frame(frame)
    line.pack(fill='x', pady=5)
    ttk.Button(line,text=t('Recover administrator…'),command=error(recover_admin)).pack(side='left',padx=(0,8))
    ttk.Button(line,text=t('Remove automatic service…'),command=error(remove)).pack(side='left')
    ttk.Label(frame,text=t('Text PDFs and Word files work immediately. For scans, choose Tesseract or a vision model in Server settings. Server errors are recorded in the logs folder.'),wraplength=680).pack(anchor='w',pady=10)
    def refresh():
        installed=service_state()
        active = running_host(directory.get())
        in_use = installation_in_use(directory.get())
        if running['process'] and running['process'].poll() is None:
            in_use = True
        if installed is not None and not (running['process'] and running['process'].poll() is None):
            if Path(directory.get()).resolve()!=service_data().resolve():
                directory.set(str(service_data()));settings=load_settings(directory.get());port.set(str(settings['port']));tls.set(settings['https'])
            status.set({1:t('Service stopped'),2:t('Service starting…'),3:t('Service stopping…'),4:t('Running as a Windows service')}.get(installed,t('Service is changing state…')))
            in_use = installed != 1
        elif active:
            port.set(str(active['port']))
            tls.set(active['https'])
            status.set(t('Running · this window can be closed and reopened'))
        elif in_use:
            status.set(t('This folder is in use by a server started outside this launcher.'))
        elif running['process']:
            code=running['process'].poll()
            status.set(t('Running · close this window to leave the server running') if code is None else (t('Stopped') if code==0 else t('Could not start. Check the port and logs/server.log.')))
            if code is not None:folder_entry.configure(state='normal')
        else:
            status.set(t('Stopped'))
        for control in (folder_entry, browse_button, port_entry, tls_button):
            control.configure(state='disabled' if in_use else 'normal')
        urls.set('   '.join(('https' if tls.get() else 'http')+'://'+a+':'+port.get() for a in addresses() if a!='127.0.0.1') or url())
        path=Path(directory.get())/'setup-code.txt'
        try:setup.set(path.read_text().strip() if path.exists() else t('Start the server, or sign in if setup is already complete.'))
        except OSError:setup.set(t('Open the data folder on the server to read setup-code.txt.'))
    try:
        load()
    except (OSError, ValueError, TypeError) as exc:
        port.set('8443')
        tls.set(True)
        messagebox.showerror(t('Check server settings'), str(exc), parent=root)
    def tick():
        try:refresh()
        except Exception:pass
        root.after(2000,tick)
    if self_check:
        root.update_idletasks()
        assert frame.winfo_children(), 'Launcher controls did not initialize'
        root.destroy()
    else:
        tick()
        root.mainloop()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Legal Library Server')
    parser.add_argument('--serve',action='store_true')
    parser.add_argument('--data-dir',default=str(data_root()))
    parser.add_argument('--service-dispatch',action='store_true')
    parser.add_argument('--install-service',action='store_true')
    parser.add_argument('--operator-sid')
    parser.add_argument('--service-action',choices=['start','stop','remove'])
    parser.add_argument('--allow-lan',type=int)
    parser.add_argument('--self-check',action='store_true',help='Verify bundled desktop and PDF components without starting a server')
    args=parser.parse_args(argv)
    if args.self_check:
        import pymupdf
        os.environ['LEGAL_PLATFORM_DATA_DIR'] = args.data_dir
        launch(self_check=True)
        folder=Path(args.data_dir);folder.mkdir(parents=True,exist_ok=True)
        (folder/'self-check.json').write_text(json.dumps({'desktop':'ok','launcher_controls':'ok','pdf':pymupdf.VersionBind}))
        return
    if args.service_dispatch:
        from legal_platform.windows_service import dispatch
        dispatch();return
    if args.serve:
        from legal_platform.host import run_server
        run_server(args.data_dir);return
    if args.install_service or args.service_action or args.allow_lan:
        try:
            from legal_platform.windows_service import install,manage,allow_private_lan
            if args.install_service:install(args.data_dir,args.operator_sid)
            elif args.service_action:manage(args.service_action)
            else:allow_private_lan(args.allow_lan)
        except Exception as exc:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0,str(exc),'Legal Library Server',0x10)
            raise SystemExit(1)
        return
    os.environ['LEGAL_PLATFORM_DATA_DIR']=args.data_dir
    launch()


if __name__=='__main__':main()
