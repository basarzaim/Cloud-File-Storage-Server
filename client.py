# client.py
import socket
import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import threading
from datetime import datetime
import select

class ClientApp:
    def __init__(self, root):
        self.root = root
        self.root.title("File Sharing Client")

        # Socket and username
        self.client_socket = None
        self.username = None

        # Lock to synchronize socket access
        self.socket_lock = threading.Lock()

        # Flags and paths for downloading
        self.is_downloading = False
        self.download_save_path = ""

        # Login Frame
        self.login_frame = tk.Frame(self.root)
        self.login_frame.pack(pady=20)

        # Server IP input
        tk.Label(self.login_frame, text="Server IP:").pack(side=tk.LEFT, padx=5)
        self.server_ip_entry = tk.Entry(self.login_frame, width=15)
        self.server_ip_entry.pack(side=tk.LEFT, padx=5)
        self.server_ip_entry.insert(0, "127.0.0.1")  # Default IP

        # Port input
        tk.Label(self.login_frame, text="Port:").pack(side=tk.LEFT, padx=5)
        self.port_entry = tk.Entry(self.login_frame, width=10)
        self.port_entry.pack(side=tk.LEFT, padx=5)

        # Username input
        tk.Label(self.login_frame, text="Username:").pack(side=tk.LEFT, padx=5)
        self.username_entry = tk.Entry(self.login_frame, width=15)
        self.username_entry.pack(side=tk.LEFT, padx=5)

        # Connect button
        tk.Button(self.login_frame, text="Connect", command=self.connect_to_server).pack(side=tk.LEFT, padx=5)

        # Main Menu Frame (Hidden initially)
        self.menu_frame = tk.Frame(self.root)

        # Log box to display client activities
        self.log_listbox = tk.Listbox(self.root, height=15, width=80)
        self.log_listbox.pack(pady=10)
        self.log_listbox.pack_forget()  # Hide initially

    def log(self, message):
        """Logs a message to the client's log box with a timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.root.after(0, self._safe_log, f"{timestamp} - {message}")

    def _safe_log(self, message):
        """Inserts a log message into the log box."""
        self.log_listbox.insert(tk.END, message)
        self.log_listbox.yview(tk.END)  # Auto-scroll to the bottom

    def connect_to_server(self):
        """Connects the client to the server using provided credentials."""
        server_ip = self.server_ip_entry.get().strip()
        port = self.port_entry.get().strip()
        username = self.username_entry.get().strip()

        # Validate inputs
        if not server_ip or not port or not username:
            messagebox.showerror("Error", "All fields (IP, Port, Username) must be filled!")
            return
        if not port.isdigit():
            messagebox.showerror("Error", "Port must be a number!")
            return

        try:
            # Create and connect the client socket
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.connect((server_ip, int(port)))
            self.client_socket.sendall(username.encode())  # Send username to server

            # Receive server response
            response = self.client_socket.recv(1024).decode()
            if "ERROR" in response:
                messagebox.showerror("Error", response)
                self.client_socket.close()
                return

            self.username = username
            messagebox.showinfo("Connected", f"Connected to the server as {username}!")
            self.log_listbox.pack()
            self.show_main_menu()
            self.log(f"Connected to {server_ip}:{port} as {username}.")

            # Start periodic notification checks
            self.periodic_check_notifications()

        except ConnectionRefusedError:
            messagebox.showerror("Error", "Unable to connect to the server. Is it running?")
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred: {e}")

    def show_main_menu(self):
        """Displays the main menu after successful connection."""
        self.login_frame.pack_forget()
        self.menu_frame.pack(pady=20)

        # Upload File button
        tk.Button(self.menu_frame, text="Upload File", command=self.upload_file).pack(fill=tk.X, pady=5)
        # List Files button
        tk.Button(self.menu_frame, text="List Files", command=self.list_files).pack(fill=tk.X, pady=5)
        # Download File button
        tk.Button(self.menu_frame, text="Download File", command=self.download_file).pack(fill=tk.X, pady=5)
        # Delete File button
        tk.Button(self.menu_frame, text="Delete File", command=self.delete_file).pack(fill=tk.X, pady=5)
        # Exit button
        tk.Button(self.menu_frame, text="Exit", command=self.exit_app).pack(fill=tk.X, pady=5)

    def upload_file(self):
        """Initiates the file upload process."""
        filepath = filedialog.askopenfilename(title="Select a File to Upload")
        if not filepath:
            return
        threading.Thread(target=self.upload_file_thread, args=(filepath,), daemon=True).start()

    def upload_file_thread(self, filepath):
        """Handles the file upload in a separate thread."""
        filename = os.path.basename(filepath)
        try:
            with self.socket_lock:
                # Send "UPLOAD" command to the server
                self.client_socket.sendall(b"UPLOAD")
                # Send the filename
                self.client_socket.sendall(filename.encode())

                # Open and read the file in binary mode
                with open(filepath, "rb") as f:
                    while True:
                        chunk = f.read(65536)  # Read in 64 KB chunks
                        if not chunk:
                            break
                        # Send the size of the chunk followed by the chunk itself
                        chunk_size = len(chunk).to_bytes(4, byteorder="big")
                        self.client_socket.sendall(chunk_size + chunk)

                # Send EOF marker with size 0
                self.client_socket.sendall((0).to_bytes(4, byteorder="big"))
                # Receive server response
                response = self.client_socket.recv(1024).decode()
                messagebox.showinfo("Upload", response)
                self.log(f"Uploaded file: {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during file upload: {e}")
            self.log(f"Error during upload: {e}")

    def list_files(self):
        """Requests the list of available files from the server."""
        try:
            with self.socket_lock:
                # Send "LIST" command to the server
                self.client_socket.sendall(b"LIST")
                # Receive the list of files
                response = self.client_socket.recv(4096).decode()
                if response.strip() == "No files available on the server.":
                    messagebox.showinfo("File List", response.strip())
                else:
                    messagebox.showinfo("File List", f"Available Files:\n{response}")
                self.log("Requested file list.")

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while listing files: {e}")
            self.log(f"Error listing files: {e}")

    def download_file(self):
        """Initiates the file download process."""
        filename = simpledialog.askstring("Download File", "Enter the filename to download:")
        if not filename:
            return

        uploader_name = simpledialog.askstring("Uploader Name", "Enter the uploader's name:")
        if not uploader_name:
            return

        save_path = filedialog.asksaveasfilename(title="Save File As", initialfile=filename)
        if not save_path:
            self.log("Download canceled by user.")
            return

        # Start the download in a separate thread
        threading.Thread(target=self.download_file_thread, args=(filename, uploader_name, save_path), daemon=True).start()

    def download_file_thread(self, filename, uploader_name, save_path):
        """Handles the file download in a separate thread."""
        try:
            # Acquire the socket lock before starting the download
            self.socket_lock.acquire()
            self.is_downloading = True
            self.download_save_path = save_path

            # Send "DOWNLOAD" command and request
            self.client_socket.sendall(b"DOWNLOAD")
            self.client_socket.sendall(f"{filename},{uploader_name}".encode())
            self.log(f"Requested download of '{filename}' from '{uploader_name}'.")

            # Receive server response
            status = self.client_socket.recv(1024).decode().strip()
            if status.startswith("OK"):
                self.log(f"Downloading file '{filename}' from '{uploader_name}'...")
                # Open the file in binary write mode
                with open(save_path, "wb") as f:
                    while True:
                        # Receive the size of the next chunk (4 bytes)
                        chunk_size_data = self.client_socket.recv(4)
                        if not chunk_size_data:
                            raise Exception("Connection closed unexpectedly during chunk size reception.")

                        chunk_size = int.from_bytes(chunk_size_data, byteorder="big")
                        if chunk_size == 0:
                            break  # EOF marker received

                        # Receive the actual data chunk
                        chunk = b""
                        while len(chunk) < chunk_size:
                            data = self.client_socket.recv(min(65536, chunk_size - len(chunk)))
                            if not data:
                                raise Exception("Connection closed unexpectedly during file data reception.")
                            chunk += data
                        f.write(chunk)
                messagebox.showinfo("Download", f"File downloaded successfully and saved to '{save_path}'")
                self.log(f"Downloaded file: {filename}")
            elif status.startswith("ERROR"):
                messagebox.showerror("Download Error", status)
                self.log(f"Download failed: {status}")
            else:
                messagebox.showerror("Download Error", "Received unknown response from server.")
                self.log("Download failed: Unknown response from server.")

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during file download: {e}")
            self.log(f"Error during download: {e}")
            # Remove the partially downloaded file if it exists
            if os.path.exists(save_path):
                os.remove(save_path)
        finally:
            # Reset download flags and release the lock
            self.is_downloading = False
            self.download_save_path = ""
            self.socket_lock.release()

    def delete_file(self):
        """Initiates the file deletion process."""
        filename = simpledialog.askstring("Delete File", "Enter the filename to delete:")
        if not filename:
            return

        try:
            with self.socket_lock:
                # Send "DELETE" command to the server
                self.client_socket.sendall(b"DELETE")
                # Send the filename to delete
                self.client_socket.sendall(filename.encode())

                # Receive server response
                response = self.client_socket.recv(1024).decode()
                messagebox.showinfo("Delete File", response)
                self.log(f"Deleted file: {filename}")

        except Exception as e:
            messagebox.showerror("Error", f"An error occurred during file deletion: {e}")
            self.log(f"Error deleting file: {e}")

    def exit_app(self):
        """Closes the connection and exits the application."""
        try:
            if self.client_socket:
                with self.socket_lock:
                    self.client_socket.sendall(b"EXIT")
                self.client_socket.close()
                self.log("Disconnected from server.")
        except Exception:
            pass
        self.root.quit()

    def periodic_check_notifications(self):
        """
        Periodically checks for incoming notifications from the server.
        Uses Tkinter's after method to schedule the next check.
        """
        try:
            # Attempt to acquire the socket lock without blocking
            acquired = self.socket_lock.acquire(blocking=False)
            if acquired:
                try:
                    # Use select to check if there's data to read (timeout=0 for non-blocking)
                    ready_to_read, _, _ = select.select([self.client_socket], [], [], 0)
                    if ready_to_read:
                        data = self.client_socket.recv(4096).decode()
                        if not data:
                            self.log("Server closed the connection.")
                            self.client_socket.close()
                            return
                        # Split the data by newline in case multiple messages are received
                        messages = data.split('\n')
                        for message in messages:
                            if not message:
                                continue  # Skip empty messages

                            if message.startswith("NOTIFICATION:"):
                                # Extract and display the notification
                                notification = message[len("NOTIFICATION:"):].strip()
                                if notification:
                                    messagebox.showinfo("Notification", notification)
                                    self.log(f"Received notification: {notification}")
                            elif message.startswith("ERROR") or message.startswith("OK"):
                                # These are responses to commands and are already handled
                                continue
                            else:
                                # Handle any other unsolicited messages
                                self.log(f"Received message: {message}")
                finally:
                    self.socket_lock.release()
        except Exception as e:
            self.log(f"Error checking for notifications: {e}")
        finally:
            # Schedule the next check after 1000 milliseconds (1 second)
            self.root.after(1000, self.periodic_check_notifications)

if __name__ == "__main__":
    root = tk.Tk()
    app = ClientApp(root)
    root.mainloop()
