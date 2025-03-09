# server.py
import os
import socket
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from threading import Lock
import json

class ServerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("File Sharing Server")
        self.server_socket = None
        self.upload_dir = None
        self.clients = {}  # Maps client names to their sockets
        self.uploaders = {}  # Maps uploader names to their sockets
        self.uploader_files = {}  # Maps uploader names to list of their uploaded files
        self.file_lock = Lock()  # Ensures thread-safe access to uploaded_files and uploader_files
        self.notifications_lock = Lock()  # Ensures thread-safe access to notifications

        # Initialize GUI elements
        self.setup_gui()

        # Initialize data structures
        self.uploaded_files_file = "uploaded_files.json"
        self.uploaded_files = []
        self.load_uploaded_files()

        self.uploader_files_file = "uploader_files.json"
        self.load_uploader_files()

        self.notifications_file = "notifications.json"
        self.notifications = {}
        self.load_notifications()

    def setup_gui(self):
        """Sets up the server GUI."""
        frame_top = tk.Frame(self.root)
        frame_top.pack(pady=10)

        # Port input
        tk.Label(frame_top, text="Port:").pack(side=tk.LEFT)
        self.port_entry = tk.Entry(frame_top, width=10)
        self.port_entry.pack(side=tk.LEFT, padx=5)

        # Browse upload directory button
        tk.Button(frame_top, text="Browse Upload Directory", command=self.select_directory).pack(side=tk.LEFT, padx=5)
        self.dir_label = tk.Label(frame_top, text="No directory selected", width=30, anchor="w")
        self.dir_label.pack(side=tk.LEFT, padx=5)

        # Start server button
        tk.Button(self.root, text="Start Server", command=self.start_server).pack(pady=10)

        # Log box to display server activities
        self.log_listbox = tk.Listbox(self.root, height=15, width=80)
        self.log_listbox.pack(pady=10)

        # Stop server button
        tk.Button(self.root, text="Stop Server", command=self.stop_server).pack(pady=10)

    def log(self, message):
        """Logs a message to the server's log box."""
        self.log_listbox.insert(tk.END, message)
        self.log_listbox.yview(tk.END)  # Auto-scroll to the bottom

    def select_directory(self):
        """Opens a dialog to select the upload directory."""
        self.upload_dir = filedialog.askdirectory(title="Select Upload Directory")
        if self.upload_dir:
            self.dir_label.config(text=self.upload_dir)

    def start_server(self):
        """Starts the server to listen for incoming connections."""
        port = self.port_entry.get()
        if not port.isdigit():
            messagebox.showerror("Error", "Invalid port number!")
            return
        if not self.upload_dir:
            messagebox.showerror("Error", "Please select an upload directory!")
            return

        port = int(port)

        # Create and bind the server socket
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind(("0.0.0.0", port))
        self.server_socket.listen(5)  # Listen for up to 5 connections
        self.log(f"Server started on port {port}, listening for connections...")
        self.log(f"Upload directory: {self.upload_dir}")

        # Start a new thread to accept incoming connections
        threading.Thread(target=self.accept_connections, daemon=True).start()

    def accept_connections(self):
        """Continuously accepts new client connections."""
        while True:
            try:
                client_socket, client_address = self.server_socket.accept()
                threading.Thread(target=self.handle_client, args=(client_socket,), daemon=True).start()
            except Exception as e:
                self.log(f"Error accepting connection: {e}")
                break

    def handle_client(self, client_socket):
        """Handles communication with a connected client."""
        client_name = None
        try:
            # Receive the client's username
            client_name = client_socket.recv(1024).decode().strip()
            if not client_name:
                client_socket.close()
                return
            if client_name in self.clients:
                # Username already in use
                error_message = "ERROR: Name already in use. Connection closed.\n"
                client_socket.sendall(error_message.encode())
                client_socket.close()
                return

            # Add client to the clients and uploaders dictionaries
            self.clients[client_name] = client_socket
            self.uploaders[client_name] = client_socket
            self.log(f"{client_name} connected.")
            welcome_message = "Welcome to the server!\n"
            client_socket.sendall(welcome_message.encode())

            # Initialize uploader_files entry if not present
            with self.file_lock:
                if client_name not in self.uploader_files:
                    self.uploader_files[client_name] = []
                    self.save_uploader_files()

            # Continuously listen for client commands
            while True:
                request = client_socket.recv(1024).decode().strip()
                if not request:
                    break  # Client disconnected

                if request == "UPLOAD":
                    self.handle_file_upload(client_socket, client_name)
                elif request == "LIST":
                    self.handle_list_files(client_socket)
                elif request == "DOWNLOAD":
                    self.handle_file_download(client_socket, client_name)
                elif request == "DELETE":
                    self.handle_file_deletion(client_socket, client_name)
                elif request == "NOTIFICATIONS":
                    self.handle_notifications(client_socket, client_name)
                elif request == "EXIT":
                    self.log(f"{client_name} disconnected.")
                    del self.clients[client_name]
                    del self.uploaders[client_name]
                    break
                else:
                    # Unknown command received
                    error_message = "ERROR: Unknown command.\n"
                    client_socket.sendall(error_message.encode())

        except Exception as e:
            self.log(f"Error with client '{client_name}': {e}")
        finally:
            # Clean up client connection
            client_socket.close()
            if client_name in self.clients:
                del self.clients[client_name]
            if client_name in self.uploaders:
                del self.uploaders[client_name]
            self.log(f"{client_name} disconnected.")

    def handle_file_upload(self, client_socket, client_name):
        """Handles file upload from a client."""
        try:
            # Receive the filename from the client
            filename = client_socket.recv(1024).decode().strip()
            if not filename:
                raise Exception("No filename received.")

            unique_filename = f"{client_name}_{filename}"
            filepath = os.path.join(self.upload_dir, unique_filename)

            # Receive the file data in chunks
            with open(filepath, "wb") as f:
                while True:
                    # Receive the size of the next chunk
                    chunk_size_data = client_socket.recv(4)
                    if not chunk_size_data:
                        raise Exception("Connection closed unexpectedly during chunk size reception.")
                    chunk_size = int.from_bytes(chunk_size_data, byteorder="big")
                    if chunk_size == 0:
                        break  # EOF marker received

                    # Receive the actual data chunk
                    data = b""
                    while len(data) < chunk_size:
                        packet = client_socket.recv(chunk_size - len(data))
                        if not packet:
                            raise Exception("Connection closed unexpectedly during file data reception.")
                        data += packet
                    f.write(data)

            # Update the uploaded_files and uploader_files dictionaries
            with self.file_lock:
                self.uploaded_files.append((filename, unique_filename, client_name))
                self.save_uploaded_files()

                self.uploader_files[client_name].append(filename)
                self.save_uploader_files()

            self.log(f"File '{filename}' uploaded by '{client_name}'.")
            success_message = "File uploaded successfully.\n"
            client_socket.sendall(success_message.encode())

        except Exception as e:
            self.log(f"Error during file upload by '{client_name}': {e}")
            error_message = "ERROR: An error occurred during file upload.\n"
            client_socket.sendall(error_message.encode())

    def handle_file_download(self, client_socket, client_name):
        """Handles file download request from a client."""
        try:
            # Receive download request in the format "filename,owner"
            request = client_socket.recv(1024).decode().strip()
            if not request:
                raise Exception("No download request received.")
            if "," not in request:
                raise Exception("Invalid download request format.")

            filename, owner = request.split(",", 1)
            unique_filename = f"{owner}_{filename}"
            filepath = os.path.join(self.upload_dir, unique_filename)

            if os.path.exists(filepath):
                # Notify the client that the file is available
                client_socket.sendall(b"OK")
                self.log(f"Sending file '{unique_filename}' to '{client_name}'...")

                # Send the file in chunks
                with open(filepath, "rb") as f:
                    while True:
                        chunk = f.read(65536)  # Read in 64 KB chunks
                        if not chunk:
                            break
                        chunk_size = len(chunk).to_bytes(4, byteorder="big")
                        client_socket.sendall(chunk_size + chunk)

                # Send EOF marker
                client_socket.sendall((0).to_bytes(4, byteorder="big"))
                self.log(f"File '{unique_filename}' sent to '{client_name}'.")

                # Create a notification for the uploader
                notification = f"Your file '{filename}' was downloaded by {client_name}."
                with self.notifications_lock:
                    if owner in self.notifications:
                        self.notifications[owner].append(notification)
                    else:
                        self.notifications[owner] = [notification]
                    self.save_notifications()
                self.log(f"Notification stored for '{owner}': '{notification}'")

                # If the uploader is online, send the notification immediately
                with self.file_lock:
                    if owner in self.uploaders:
                        try:
                            uploader_socket = self.uploaders[owner]
                            real_time_message = f"NOTIFICATION:{notification}\n"
                            uploader_socket.sendall(real_time_message.encode())
                            self.log(f"Real-time notification sent to '{owner}'.")
                        except Exception as e:
                            self.log(f"Failed to send real-time notification to '{owner}': {e}")
            else:
                # File not found; notify the client
                error_message = "ERROR: File not found.\n"
                client_socket.sendall(error_message.encode())
                self.log(f"File '{unique_filename}' requested by '{client_name}' not found.")

        except Exception as e:
            self.log(f"Error during file download by '{client_name}': {e}")
            error_message = "ERROR: An error occurred during file download.\n"
            client_socket.sendall(error_message.encode())

    def handle_list_files(self, client_socket):
        """Sends a list of available files to the client."""
        try:
            with self.file_lock:
                if not self.uploaded_files:
                    no_files_message = "No files available on the server.\n"
                    client_socket.sendall(no_files_message.encode())
                    self.log("Client requested file list: No files available.")
                else:
                    # Format the file list for the client
                    files_list = "\n".join([f"{file} (Uploaded by: {owner})" for file, _, owner in self.uploaded_files])
                    client_socket.sendall(files_list.encode())
                    self.log("Sent file list to client.")
        except Exception as e:
            self.log(f"Error during file listing: {e}")
            error_message = "ERROR: An error occurred during file listing.\n"
            client_socket.sendall(error_message.encode())

    def handle_file_deletion(self, client_socket, client_name):
        """Handles file deletion request from a client."""
        try:
            # Receive the filename to delete
            filename = client_socket.recv(1024).decode().strip()
            if not filename:
                raise Exception("No filename received for deletion.")

            unique_filename = f"{client_name}_{filename}"
            filepath = os.path.join(self.upload_dir, unique_filename)

            if os.path.exists(filepath):
                # Remove the file from the server
                os.remove(filepath)
                with self.file_lock:
                    # Remove the file from the uploaded_files list
                    self.uploaded_files = [(f, u, o) for f, u, o in self.uploaded_files if u != unique_filename]
                    self.save_uploaded_files()

                    # Remove the file from uploader_files
                    if client_name in self.uploader_files:
                        if filename in self.uploader_files[client_name]:
                            self.uploader_files[client_name].remove(filename)
                            self.save_uploader_files()

                self.log(f"File '{filename}' deleted by '{client_name}'.")
                success_message = "File deleted successfully.\n"
                client_socket.sendall(success_message.encode())
            else:
                # File not found; notify the client
                error_message = "ERROR: File not found.\n"
                client_socket.sendall(error_message.encode())
                self.log(f"File '{unique_filename}' requested by '{client_name}' not found for deletion.")
        except Exception as e:
            self.log(f"Error during file deletion by '{client_name}': {e}")
            error_message = "ERROR: An error occurred during file deletion.\n"
            client_socket.sendall(error_message.encode())

    def handle_notifications(self, client_socket, client_name):
        """Sends stored notifications to the client upon request."""
        try:
            with self.notifications_lock:
                notifications = self.notifications.get(client_name, [])
                if notifications:
                    # Send all notifications to the client
                    notifications_str = "\n".join(notifications)
                    client_socket.sendall(notifications_str.encode())
                    # Clear notifications after sending
                    self.notifications[client_name] = []
                    self.save_notifications()
                    self.log(f"Sent notifications to '{client_name}'.")
                else:
                    # No new notifications
                    client_socket.sendall(b"No new notifications.\n")
                    self.log(f"No notifications for '{client_name}'.")
        except Exception as e:
            self.log(f"Error during notifications handling for '{client_name}': {e}")
            error_message = "ERROR: An error occurred during notifications retrieval.\n"
            client_socket.sendall(error_message.encode())

    def stop_server(self):
        """Stops the server and closes all connections."""
        try:
            if self.server_socket:
                self.server_socket.close()
            self.log("Server stopped.")
            self.root.destroy()
        except Exception as e:
            self.log(f"Error stopping server: {e}")

    def load_uploaded_files(self):
        """Loads the list of uploaded files from a JSON file."""
        if os.path.exists(self.uploaded_files_file):
            with open(self.uploaded_files_file, 'r') as f:
                self.uploaded_files = json.load(f)
                self.log("Uploaded files list loaded from file.")
        else:
            self.uploaded_files = []
            self.log("No existing uploaded files list found.")

    def save_uploaded_files(self):
        """Saves the list of uploaded files to a JSON file."""
        with open(self.uploaded_files_file, 'w') as f:
            json.dump(self.uploaded_files, f)

    def load_uploader_files(self):
        """Loads the uploader_files dictionary from a JSON file."""
        if os.path.exists(self.uploader_files_file):
            with open(self.uploader_files_file, 'r') as f:
                self.uploader_files = json.load(f)
                self.log("Uploader files loaded from file.")
        else:
            self.uploader_files = {}
            self.log("No existing uploader files found.")

    def save_uploader_files(self):
        """Saves the uploader_files dictionary to a JSON file."""
        with open(self.uploader_files_file, 'w') as f:
            json.dump(self.uploader_files, f)

    def load_notifications(self):
        """Loads the notifications dictionary from a JSON file."""
        if os.path.exists(self.notifications_file):
            with open(self.notifications_file, 'r') as f:
                self.notifications = json.load(f)
                self.log("Notifications loaded from file.")
        else:
            self.notifications = {}
            self.log("No existing notifications found.")

    def save_notifications(self):
        """Saves the notifications dictionary to a JSON file."""
        with open(self.notifications_file, 'w') as f:
            json.dump(self.notifications, f)

    def load_json(filepath, default_value):
        """Safely loads JSON data from a file or returns a default value if an error occurs."""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r') as f:
                    return json.load(f)
            else:
                return default_value
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading JSON file {filepath}: {e}")
            return default_value


if __name__ == "__main__":
    root = tk.Tk()
    app = ServerApp(root)
    app.load_uploader_files()  # Load uploader_files after initialization
    root.mainloop()
