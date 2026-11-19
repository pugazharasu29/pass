import tkinter as tk
from tkinter import filedialog, messagebox
import mysql.connector
import qrcode
from PIL import Image, ImageTk
import os

# Database Configuration
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "digibuspass"
}

def fetch_pass():
    """Fetch user details from the database and generate the pass."""
    name = name_entry.get()
    
    if not name:
        messagebox.showerror("Error", "Enter a name to fetch details")
        return
    
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # Fetch user details
        cursor.execute("SELECT pass_type, validity, route, photo_path FROM personal_details WHERE name = %s", (name,))
        user_data = cursor.fetchone()
        
        if not user_data:
            messagebox.showerror("Error", "No record found for this name")
            return
        
        pass_type, validity, route, photo = user_data
        
        # Display retrieved details in UI fields
        pass_type_entry.delete(0, tk.END)
        pass_type_entry.insert(0, pass_type)

        validity_entry.delete(0, tk.END)
        validity_entry.insert(0, validity)

        route_entry.delete(0, tk.END)
        route_entry.insert(0, route)

        photo_path.set(photo)

        # Display photo
        if os.path.exists(photo):
            img = Image.open(photo)
            img = img.resize((100, 100), Image.Resampling.LANCZOS)
            img = ImageTk.PhotoImage(img)
            photo_label.config(image=img)
            photo_label.image = img

        # Generate QR code
        generate_qr_code(name, pass_type, validity, route)

        messagebox.showinfo("Success", "Bus pass retrieved successfully")

    except Exception as e:
        messagebox.showerror("Database Error", str(e))
    finally:
        cursor.close()
        conn.close()

def generate_qr_code(name, pass_type, validity, route):
    """Generate and display QR Code for the bus pass."""
    qr_data = f"Name: {name}\nPass Type: {pass_type}\nValidity: {validity}\nRoute: {route}"
    qr = qrcode.make(qr_data)
    qr_path = f"{name}_qrcode.png"
    qr.save(qr_path)
    
    img = Image.open(qr_path)
    img = img.resize((100, 100), Image.Resampling.LANCZOS)
    img = ImageTk.PhotoImage(img)
    qr_label.config(image=img)
    qr_label.image = img

def create_ui():
    """Create the UI for the bus pass generator."""
    global name_entry, pass_type_entry, validity_entry, route_entry, photo_path, photo_label, qr_label
    
    root = tk.Tk()
    root.title("DigiBusPass Generator")
    root.geometry("400x600")
    root.configure(bg="#f4f4f4")
    
    style = {
        "font": ("Arial", 12),
        "bg": "#f4f4f4",
        "fg": "#333"
    }
    
    tk.Label(root, text="Name", **style).pack(pady=5)
    name_entry = tk.Entry(root, font=("Arial", 12))
    name_entry.pack(pady=5)
    
    tk.Label(root, text="Pass Type", **style).pack(pady=5)
    pass_type_entry = tk.Entry(root, font=("Arial", 12))
    pass_type_entry.pack(pady=5)
    
    tk.Label(root, text="Validity", **style).pack(pady=5)
    validity_entry = tk.Entry(root, font=("Arial", 12))
    validity_entry.pack(pady=5)
    
    tk.Label(root, text="Route", **style).pack(pady=5)
    route_entry = tk.Entry(root, font=("Arial", 12))
    route_entry.pack(pady=5)

    tk.Label(root, text="Photo", **style).pack(pady=5)
    photo_path = tk.StringVar()
    
    photo_label = tk.Label(root, bg="#f4f4f4")
    photo_label.pack(pady=5)
    
    tk.Button(root, text="Fetch Pass", command=fetch_pass, font=("Arial", 12), bg="#28A745", fg="white").pack(pady=10)
    
    qr_label = tk.Label(root, bg="#f4f4f4")
    qr_label.pack(pady=5)
    
    root.mainloop()

if __name__ == "__main__":
    create_ui()

