# Legal Library — start here

One Windows computer hosts the library. Your colleagues open its address in a browser; they do not install anything. Keep the host awake and connected to your network.

## First start

1. Extract the entire Windows ZIP to a folder you want to keep. Keep `LegalLibrary.exe` and `_internal` together.
2. Open **LegalLibrary.exe**. Choose a data folder on a local drive. The default is your Windows account’s `AppData/Local/LegalPlatform/data` folder.
3. Keep **Use HTTPS** checked and choose **Start server**. The default port is **8443**.
4. Choose **HTTPS certificate…** to export this installation’s public certificate. Have your IT administrator trust it on the browsers that will use the library. The dialog shows its fingerprint so it can be checked. An organization-issued certificate can replace `tls/server.crt` and `tls/server.key` while the server is stopped. Keep the private key on the host.
5. Choose **Open library**. Copy the setup code from the launcher into the page, then create your administrator account. Use a password of at least 12 characters. The setup code disappears after the first account is created.
6. Create a **Collection**, upload a text PDF or Word `.docx` file, and wait until it says **Ready**. Open **Ask your documents**, choose the collection, and ask a specific question.

For a quick test on the host alone, you can turn HTTPS off and open `http://localhost:8443`. Use trusted HTTPS before sending passwords or private documents across a network.

## Let colleagues use it

- In the launcher, choose **Allow LAN access…**. Windows asks for administrator approval. The rule allows the selected port on Private networks from the local subnet.
- Share an address shown in the launcher, such as `https://192.168.1.20:8443`. Keep the port number. A stable host address avoids changes after restart.
- In the library, open **People → Create invitation** and send the one-use link privately to your colleague. Alternatively, they can sign up and wait for your approval in **People**.
- Open the collection’s **Sharing** settings and add them. A new account does not automatically have access to everyone’s documents.
- **Viewer** can search and read; **Contributor** can also upload; **Manager** can manage the collection. The collection owner retains control.

Do not forward the port on your Internet router. This release is designed for one organization on a managed LAN. A public hosted service needs an HTTPS deployment with a trusted domain, operational monitoring, a privacy policy, and the additional release checks in the repository README.

## Run after Windows restarts

1. Choose **Stop server** and wait for it to stop.
2. Choose **Install as service…** and approve the Windows administrator prompt.
3. The application is copied to `C:\Program Files\Legal Library`. The library is copied to `C:\ProgramData\LegalLibrary\data`; the earlier copy is kept.
4. The **Legal Library** service starts automatically, using Windows’ limited **Local Service** account. The launcher switches to the service’s data folder. Its Start and Stop buttons then control that service.

The host must stay powered on and awake. Service installation does not change your sleep settings. Removing the service keeps program files and documents for recovery.

The launcher remembers the last data folder you started. You can close and reopen it to control a running launcher-owned server. Port and folder controls are disabled while that server is running; stop it before changing them. On smaller screens, scroll the launcher to reach all controls.

## Daily use

**Documents:** upload several files or select a folder. Check the preview, names, collection and optional dates before uploading. Each file is tracked separately; retrying a failed batch skips the files already uploaded. Limits are 25 MB per file and 50 files per batch. The default server document-storage limit is 2 GB.

**Sources:** answers contain quotations from extracted source text, with the exact source version attached. Open **Inspect source** and compare with **Download original**. Word extraction does not reproduce printed page layout. OCR can misread scans; inspect the original before relying on numbers or legal wording.

**Dates:** “Effective on” uses dates entered on your documents. Undated sources are marked. The app does not automatically establish which law supersedes another or whether your collection contains every relevant document.

**Versions:** a collection manager can open document Details and choose **Upload new version**. New searches use the active version; saved citations keep their original version. Archive documents to remove them from normal search; restore them when needed.

**Saved answers:** questions and references are saved privately to your account. Copy or download them with references and record feedback. Losing access to a source collection also removes access to saved answers that cite it.

**Accounts:** change your name, email and password and sign out individual sessions from your account page. Administrators approve or disable accounts and create one-use recovery codes. Changing or resetting a password signs out existing sessions. There is no email delivery service to configure: invitations and recovery codes are given to the recipient by the administrator.

If every administrator is locked out, the trusted host operator can stop the server and choose **Recover administrator…** in the launcher. Enter the username of an existing active administrator and a new password. This signs out that account's devices, invalidates its recovery codes and records the recovery. It cannot create or promote an account. Start the server again and sign in. Keep two trusted administrators for ordinary account recovery.

## Scanned PDFs

Text PDFs and Word files work without installing OCR. Scanned PDFs need a Tesseract installation with **Vietnamese and English language data** on the host. The app finds the standard `C:\Program Files\Tesseract-OCR\tesseract.exe` location, or the administrator can set `LEGAL_PLATFORM_TESSERACT` to the executable path. Restart the server after changing this setting and retry the affected document.

Use the installation options linked from [Tesseract’s documentation](https://tesseract-ocr.github.io/tessdoc/Installation.html). Mixed PDFs are checked page by page; an unreadable scan is reported instead of quietly omitted. Blank or very short pages may also need manual attention.

## Optional AI

Local mode works immediately and keeps document search on the host. In **Server settings**, an administrator can approve and configure an Ollama-compatible server with a chat model and an embedding model. AI mode sends questions and relevant passages to that destination. The model selects passages, and the server checks the quotations; it does not present generated legal conclusions as verified facts.

Changing search models queues ready documents to rebuild their search data. If a provider fails, fix its settings or switch back to local mode. No external AI destination or credential is preconfigured.

## Backup and recovery

Choose **Back up library…** in the launcher. Enter and confirm a passphrase of at least 12 characters. Store the resulting `.legalbackup` file separately from the host and keep its passphrase safe. It includes accounts, source versions and provider settings in encrypted form. The passphrase cannot be recovered.

To restore, choose **Restore backup…**, select the backup and a **new, empty folder**, then enter the passphrase. The existing library is never overwritten. Stop the current server, browse to the restored data folder and start it. Users must sign in again. HTTPS certificates are created for the restored host rather than carried over from the backup.

For service recovery, have the host administrator stop the service and put the verified restored data into its data folder while preserving the original as a separate recovery copy. Keep the service account’s access permissions. Test backups periodically, not just after a failure.

## If something goes wrong

| What you see | What to do |
|---|---|
| The server cannot start | Check whether the port is already used or another server is using that data folder. Choose another port or stop the other instance. |
| A colleague cannot connect | Check the displayed address, network connection, host sleep settings, Private-network firewall rule and certificate trust. |
| A document needs attention | Open Details, read the reason, fix OCR or source quality, then choose Retry. Processing interrupted by a restart is also marked for retry. |
| No useful answer | Choose the right collection, verify document dates, try distinctive wording or add the missing source. |
| Forgotten password | Ask another administrator for a recovery code, then use “Forgot password?” on the sign-in page. Keep two trusted administrators to avoid a single point of account recovery. |
| Service upgrade | Back up, stop the service, and have the Windows administrator replace the program folder contents with the new complete package. Keep the data folder. Start and verify the library before deleting the previous package. |

The launcher’s **Open data folder** button gives access to `logs/server.log`. Logs rotate automatically. Back up before changing the data folder or replacing an installation.
