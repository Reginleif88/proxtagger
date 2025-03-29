# 🧩 ProxTagger

![Overview image](https://res.cloudinary.com/dh1qu2two/image/upload/v1743217553/Screenshot_2025-03-29_025011_i45y0z.png)

A lightweight, open-source web interface to bulk manage Proxmox VM and container tags with backup and restore functionality.

![License](https://img.shields.io/github/license/Reginleif88/proxtagger?label=license)
![Python](https://img.shields.io/badge/python-3.6%2B-blue)
![Flask](https://img.shields.io/badge/flask-3.1.0-green)

## 🌟 Overview

ProxTagger provides a simple yet powerful web interface to manage tags for your Proxmox VMs and containers. It simplifies tag management with individual and bulk operations, while also offering backup and restore functionality to safeguard your tagging system which is currently not backed up by Promox Backup Server.

## ✨ Features

- 🏷️ **Comprehensive Tag Management**
  - View all VMs and containers with their tags in one place
  - Add/remove tags to individual VMs with a clean, intuitive interface
  - Perform bulk operations to add or remove tags across multiple VMs
  - Filter and search capabilities for large environments
  
- 💾 **Backup & Restore**
  - Download tag configurations as JSON files
  - Restore tags from previous backups
  - Automatic tag backup on initial setup
  
- 🔒 **Security & Flexibility**
  - Uses Proxmox API tokens for secure authentication
  - SSL verification toggle for self-signed certificates
  - Uses official Promox APIs

## 🚀 Getting Started

### Prerequisites

- Python 3.6+
- A Proxmox VE server
- API token with appropriate permissions (`VM.Audit` and `VM.Config.Options`)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/reginleif88/proxtagger.git
   cd proxtagger
   ```

2. Install dependencies or do it in virtual env:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python app.py
   ```

4. Access the web interface:
   Open your browser and navigate to `http://localhost:5000` (it also binds to other interfaces, you can change it in `app.py`)

## ⚙️ Configuration

### API Token Setup

You'll need a Proxmox API token with the following permissions:
- `VM.Audit` (to list VMs and containers)
- `VM.Config.Options` (to read and modify tags)

To create an API token:
1. Log in to your Proxmox web interface
2. Navigate to Datacenter → Permissions → API Tokens
3. Click "Add" and follow the prompts
4. **Important:** Note down both the token ID/name and secret - the secret is only shown once!
5. Ensure the token has the required privileges (VM.Audit, VM.Config.Options)

### First-time Setup

1. On first launch, you'll be prompted to enter your Proxmox connection details:
   - Host (IP or domain)
   - Port (default: 8006)
   - User (e.g., root@pam)
   - Token name and value
   - SSL verification toggle (disable for self-signed certificates)

2. After successful connection, the system automatically creates an initial tag backup

## 📋 Usage Guide

### Tag Management

- **Individual Tags**: Click the "+" button next to any VM to add tags
- **Bulk Operations**: Use the "Bulk Tag Management" panel to:
  - Select multiple VMs using checkboxes
  - Choose "Add Tags" or "Remove Tags" operation
  - Select existing tags or create new ones
  - Click "Apply" to execute the changes

### Backup & Restore

- **Export Tags**: Click "Export Tags" in the sidebar to download a backup JSON file
- **Import Tags**: Click "Import Tags" and select a previously exported backup file
- **Note**: When restoring tags, the system matches VMs by VMID, Node, and Type, and replaces all existing tags with imported ones

## 🔍 Troubleshooting

### Common Issues

- **No VMs Visible**: Ensure your API token has `VM.Audit` and `VM.Config.Options` permissions at the appropriate level (/ or node-specific)
- **Connection Failed**: Check your hostname, port and network connectivity
- **SSL Errors**: Toggle off SSL verification if you're using self-signed certificates

## 🛠️ Technical Details

ProxTagger is built using:
- **Backend**: Python with Flask web framework
- **Frontend**: Bootstrap 5 with custom JavaScript
- **Storage**: Local configuration file for connection details

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the Project
2. Create your Feature Branch
3. Commit your Changes
4. Push to the Branch
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgements

- [Flask](https://flask.palletsprojects.com/) - The web framework used
- [Bootstrap](https://getbootstrap.com/) - UI framework
- [Bootstrap Icons](https://icons.getbootstrap.com/) - Icon set
- [Proxmox Team](https://www.proxmox.com/) - For their amazing virtualization platform
