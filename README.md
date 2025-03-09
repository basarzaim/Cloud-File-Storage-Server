# TXT File Cloud Storage Server

A Python-based client-server application that enables file uploads, downloads, and notifications in real-time. Designed for easy sharing of text files (though it can handle other file types as well) within a local network or over the internet.

## Features

- **User-Friendly GUI**: Built with `tkinter` for both server and client interfaces.
- **Secure File Transfers**: Uses Python’s `socket` library to handle TCP connections.
- **Notifications**: Uploader is alerted whenever someone downloads their files.
- **Multi-Client Support**: Handles multiple client connections concurrently.
- **File Management**: Users can list, upload, download, and delete files.
- **Persistent Data**: Stores metadata (file lists, notifications) in JSON files, so data remains available after server restarts.

## Technologies and Libraries

- **Python 3.x**
- **socket**: For establishing and managing TCP network connections.
- **threading**: To handle multiple client connections in parallel.
- **tkinter**: For building the GUI (both server and client).
- **os**: For file operations (creating, deleting, reading paths, etc.).
- **json**: For storing file metadata, uploader-file mappings, and notifications.
- **select**: Used in the client to check for incoming server notifications without blocking the main GUI.

## How It Works

1. **Server**  
   - Run `server.py` to start the server GUI.
   - Select the port to listen on and the directory where uploaded files will be stored.
   - Click “Start Server”; the server waits for incoming connections.

2. **Client**  
   - Run `client.py`.
   - Enter the server’s IP, port, and a username.
   - Upon successful connection, you can:
     - **Upload** a file.
     - **List** all files on the server.
     - **Download** a specific file (by entering the uploader’s username and filename).
     - **Delete** a file that you uploaded.
     - Receive real-time notifications when your files are downloaded.

3. **Notifications**  
   - Server logs every download and creates a notification for the original uploader.
   - If the uploader is currently connected, the server immediately pushes a pop-up message (real-time).
   - If the uploader is offline, the notification is saved to `notifications.json`. When the uploader next connects, it’s sent to them.

## Installation and Setup

1. **Clone the Repository**  
   ```bash
   git clone https://github.com/basarzaim/Cloud-File-Storage-Server.git
   cd cloud-file-storage-server
