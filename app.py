import logging
import json
import os
from flask import Flask, request, render_template, redirect, url_for, flash, jsonify, abort, send_file
from io import BytesIO
from datetime import datetime
from config import load_config, save_config
from proxmox_api import get_all_vms, update_vm_tags
from tag_utils import extract_tags
from backup_utils import (
    create_backup_file, 
    restore_from_backup_data
)
from modules.conditional_tags import conditional_tags_bp

app = Flask(__name__)
app.secret_key = "PI2synP8sB9gJjpDzSImXifR" # Not used
app.jinja_env.add_extension('jinja2.ext.do')

# Register blueprints
app.register_blueprint(conditional_tags_bp)

# Set up logging
logging.basicConfig(level=logging.INFO)

def validate_form_input(form):
    """Validate required fields in the form."""
    required_fields = ["host", "port", "user", "token_name", "token_value"]
    for field in required_fields:
        if not form.get(field):
            flash(f"Missing field: {field}", "danger")
            return False
    return True

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        if not validate_form_input(request.form):
            return redirect(url_for("index"))
            
        # Clean host input - remove https:// if user added it
        host = request.form["host"]
        if host.startswith("https://"):
            host = host[8:]  # Remove the "https://" prefix

        # Save config
        new_config = {
            "PROXMOX_HOST": host,
            "PROXMOX_PORT": request.form["port"],
            "PROXMOX_USER": request.form["user"],
            "PROXMOX_TOKEN_NAME": request.form["token_name"],
            "PROXMOX_TOKEN_VALUE": request.form["token_value"],
            "VERIFY_SSL": bool(request.form.get("verify_ssl"))
        }
        logging.info("Saving config: %s", new_config)
        save_config(new_config)
        
        # Save config and prepare for download + redirect
        try:
            vms = get_all_vms()
            
            # Check if we have permission to see VMs
            if len(vms) == 0:
                # Set config_ok to False in session
                return redirect(url_for("index"))
                
            flash(f"✅ Configuration saved successfully. Your JSON backup was downloaded automatically.", "success")
            return redirect(url_for("download_and_redirect"))
        except Exception as e:
            logging.error(f"Error during configuration: {e}")
            flash(f"⚠️ Connection failed: {str(e)}", "danger")
            return redirect(url_for("index"))

    # GET request: load config and try to connect
    config = load_config()
    try:
        vms = get_all_vms()
        
        # If we get here with VMs, connection was successful
        tags = extract_tags(vms)
        
        # Check for permission issues where we connect but get no VMs
        show_permission_warning = len(vms) == 0
        if show_permission_warning:
            return render_template(
                "index.html",
                config_ok=False,  # Show setup form if no VMs found
                config=config,
                error="API token may not have sufficient permissions (VM.Audit and VM.Config.Options)."
            )
            
        # Normal case: we have VMs and everything is OK    
        return render_template(
            "index.html",
            vms=vms,
            tags=tags,
            config_ok=True,
            show_permission_warning=False
        )
    except Exception as e:
        logging.error("Error fetching VMs: %s", e)
        return render_template("index.html", config_ok=False, config=config, error=str(e))

@app.route("/download-and-redirect")
def download_and_redirect():
    """Download the backup file and then redirect to the index page."""
    try:
        # Get VMs and check permissions
        vms = get_all_vms()
        
        # Check if we have permission to see VMs
        if len(vms) == 0:
            flash("⚠️ No VMs or containers were found. This may be because your Proxmox API token does not have permission to access VMs/CTs data, it may lack `VM.Audit` and `VM.Config.Options` rights at `/` or per-node level, you can fix this in the Proxmox UI under Datacenter → Permissions", "warning")
            return redirect(url_for("index"))
            
        # Create an HTML page with JavaScript that will trigger download and redirect
        download_url = url_for('backup_tags')
        redirect_url = url_for('index')
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Downloading Backup...</title>
            <script>
                window.onload = function() {{
                    // Start the download
                    window.location.href = '{download_url}';
                    
                    // Redirect after a short delay to allow download to start
                    setTimeout(function() {{
                        window.location.href = '{redirect_url}';
                    }}, 1500);
                }};
            </script>
        </head>
        <body>
            <p>Downloading backup... You will be redirected automatically.</p>
        </body>
        </html>
        """
        
        return html
    except Exception as e:
        logging.error(f"Error in download and redirect: {e}")
        flash(f"⚠️ Error preparing download: {str(e)}", "warning")
        return redirect(url_for("index"))

@app.route("/api/vms")
def api_vms():
    try:
        vms = get_all_vms()
        return jsonify(vms)
    except Exception as e:
        logging.error("Error fetching VMs: %s", e)
        abort(500, description=str(e))

@app.route("/api/tags")
def api_tags():
    try:
        vms = get_all_vms()
        tags = extract_tags(vms)
        return jsonify(tags)
    except Exception as e:
        logging.error("Error fetching tags: %s", e)
        abort(500, description=str(e))

@app.route("/api/vm/<int:vmid>/tags", methods=["PUT"])
def api_update_tags(vmid):
    data = request.json
    # Get tags, ensuring empty strings are handled correctly
    tags = data.get("tags", "").strip()
    node = data.get("node")
    vm_type = data.get("type", "qemu")  # default to qemu

    if not node or vm_type not in ["qemu", "lxc"]:
        abort(400, description="Missing or invalid data")

    try:
        update_vm_tags(node, vmid, tags, vm_type)
        return {"success": True, "tags": tags}
    except Exception as e:
        logging.error("Error updating tags for VM %d: %s", vmid, e)
        abort(500, description=str(e))


@app.route("/api/bulk-tag-update", methods=["POST"])
def api_bulk_tag_update():
    """Handle bulk tag additions or removals for multiple VMs/containers."""
    data = request.json
    operation = data.get("operation")  # "add" or "remove"
    target_tags = data.get("tags", [])  # List of tags to add/remove
    selected_vms = data.get("vms", [])  # List of VM objects with id, node, type
    
    if not operation or operation not in ["add", "remove"] or not target_tags or not selected_vms:
        return jsonify({"success": False, "error": "Missing or invalid data"}), 400
    
    try:
        # Track success and failures
        results = {
            "success": True,
            "updated": 0,
            "failed": 0,
            "failures": []
        }
        
        # Process each selected VM
        for vm in selected_vms:
            vmid = vm.get("id")
            node = vm.get("node")
            vm_type = vm.get("type")
            current_tags = vm.get("tags", "")
            
            # If node or vm_type is missing (from VMs not on current page)
            # we need to find that info from the current VM list
            if not node or not vm_type:
                try:
                    # Get fresh VM data from the API
                    all_vms = get_all_vms()
                    # Find this VM in the list
                    for current_vm in all_vms:
                        if current_vm.get("vmid") == vmid:
                            node = current_vm.get("node")
                            vm_type = current_vm.get("type")
                            current_tags = current_vm.get("tags", "")
                            break
                except Exception as e:
                    logging.error(f"Error fetching VM data for VMID {vmid}: {e}")
                    results["failed"] += 1
                    results["failures"].append({
                        "vmid": vmid,
                        "name": vm.get("name", f"VM {vmid}"),
                        "error": f"Could not retrieve VM data: {str(e)}"
                    })
                    continue  # Skip to next VM
            
            # Convert current tags to a list
            current_tag_list = [tag.strip() for tag in current_tags.split(";") if tag.strip()] if current_tags else []
            
            if operation == "add":
                # Add new tags (avoid duplicates)
                for tag in target_tags:
                    if tag and tag not in current_tag_list:
                        current_tag_list.append(tag)
            else:  # Remove operation
                # Remove specified tags
                current_tag_list = [tag for tag in current_tag_list if tag not in target_tags]
            
            # Convert back to semicolon-separated string
            # Filter out any empty tags to avoid whitespace issues
            filtered_tag_list = [tag for tag in current_tag_list if tag.strip()]
            new_tags = ";".join(filtered_tag_list)
            
            try:
                # Update the VM's tags
                update_vm_tags(node, vmid, new_tags, vm_type)
                results["updated"] += 1
            except Exception as e:
                results["failed"] += 1
                results["failures"].append({
                    "vmid": vmid,
                    "name": vm.get("name", f"VM {vmid}"),
                    "error": str(e)
                })
                logging.error(f"Error in bulk update for VM {vmid}: {e}")
        
        # If any operations failed, set success to false
        if results["failed"] > 0:
            results["success"] = False
        
        return jsonify(results)
    except Exception as e:
        logging.error(f"Error in bulk tag update: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/backup-tags")
def backup_tags():
    """Generate a JSON file with all VM/CT tags for backup."""
    try:
        vms = get_all_vms()
        buffer, filename = create_backup_file(vms)
        
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype='application/json'
        )
    except Exception as e:
        logging.error(f"Error creating tag backup: {e}")
        flash(f"⚠️ Error creating backup: {str(e)}", "danger")
        return redirect(url_for("index"))


@app.route("/api/restore-tags", methods=["POST"])
def restore_tags():
    """Restore tags from a JSON backup file."""
    if 'backup_file' not in request.files:
        return jsonify({"success": False, "error": "No file provided"}), 400
    
    file = request.files['backup_file']
    if file.filename == '':
        return jsonify({"success": False, "error": "No file selected"}), 400
    
    try:
        # Parse the JSON file
        backup_data = json.load(file)
        
        # Use the utility function to restore tags
        results = restore_from_backup_data(backup_data, update_vm_tags)
        
        # Always treat it as a success if at least some VMs were updated
        if results["updated"] > 0:
            message = f"Successfully restored tags for {results['updated']} VMs/containers"
            
            # If there were failures, add that info to the message but still show as success
            if results["failed"] > 0:
                message += f". {results['failed']} VMs/containers couldn't be updated (possibly deleted)."
                
            return jsonify({
                "success": True, 
                "message": message,
                "partial_failures": results["failed"] > 0,
                "failures": results["failures"]
            })
        else:
            # Only show error if nothing could be updated
            return jsonify({
                "success": False,
                "error": "No VMs/containers could be updated. Check if the backup file matches your current environment.",
                "failures": results["failures"]
            })
    except Exception as e:
        logging.error(f"Error restoring tags: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5660)
