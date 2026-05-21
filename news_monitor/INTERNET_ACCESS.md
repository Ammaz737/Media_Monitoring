# Internet Access Configuration

## ✅ System is Now Configured for Internet Access!

### Local Network Access URLs
Your News Monitor system is accessible at:

- **Local Network (LAN):** http://192.168.101.96:5000
- **Local Network (LAN):** http://172.16.2.96:5000
- **Localhost:** http://localhost:5000 or http://127.0.0.1:5000

### Internet Access (Public Access)

To make the system accessible from the internet, you need to:

#### Option 1: Port Forwarding (Recommended for direct access)
1. **Find your Public IP:**
   - Visit https://whatismyipaddress.com/
   
2. **Configure Router Port Forwarding:**
   - Login to your router admin panel (usually http://192.168.1.1 or http://192.168.0.1)
   - Find "Port Forwarding" or "Virtual Server" settings
   - Add a new rule:
     - **Service Name:** News Monitor
     - **External Port:** 5000 (or any port you prefer)
     - **Internal IP:** 192.168.101.96
     - **Internal Port:** 5000
     - **Protocol:** TCP
   
3. **Access from Internet:**
   - Use: http://YOUR_PUBLIC_IP:5000

#### Option 2: Reverse Proxy (Recommended for HTTPS and domain)
Use services like:
- **ngrok:** Free tunneling service
  ```powershell
  ngrok http 5000
  ```
- **Cloudflare Tunnel:** Free, with HTTPS
- **Azure App Gateway:** Enterprise solution

#### Option 3: Cloud Deployment
- Deploy on Azure/AWS/Google Cloud
- Use their load balancers for HTTPS and domain mapping

### Security Recommendations

⚠️ **IMPORTANT:** Before exposing to internet:

1. **Change Secret Key:**
   Edit `config.py` and change:
   ```python
   'secret_key': 'your-secret-key-change-this'
   ```
   to a strong random string.

2. **Add Authentication:**
   Consider adding Flask-Login or Flask-Security for user authentication.

3. **Setup HTTPS:**
   Use a reverse proxy (nginx/Apache) with SSL certificate.

4. **Restrict IP Access:**
   Configure firewall rules to allow only specific IPs if needed:
   ```powershell
   netsh advfirewall firewall set rule name="News Monitor Web Access" new remoteip=YOUR_ALLOWED_IP
   ```

5. **Use Environment Variables:**
   Store sensitive data (RTSP URLs, email passwords) in environment variables.

### Firewall Status
✅ Windows Firewall rule has been added to allow incoming connections on port 5000.

To check firewall rules:
```powershell
netsh advfirewall firewall show rule name="News Monitor Web Access"
```

To remove the rule (if needed):
```powershell
netsh advfirewall firewall delete rule name="News Monitor Web Access"
```

### Starting the Server

**Option 1: PowerShell Script (Easy)**
```powershell
.\start_production.ps1
```

**Option 2: Python Direct**
```powershell
python main.py --mode web --log-level INFO
```

**Option 3: Production Server (Best for performance)**
```powershell
# First install waitress
pip install waitress

# Then run
python run_production.py
```

### Current Configuration
- **Host:** 0.0.0.0 (all network interfaces)
- **Port:** 5000
- **Debug Mode:** Disabled (production ready)
- **Firewall:** Configured for port 5000

### Monitoring Access
Once running, you can:
1. Access the web dashboard
2. View real-time text extractions
3. Monitor audio transcriptions
4. Check alerts
5. Search historical data
6. Start/stop monitoring from the web interface

### Support
For issues or questions:
- Check logs in `logs/news_monitor.log`
- Review database at `data/news_monitor.db`
- Verify RTSP stream connectivity
- Check UTRNet model files are present

---

**System Status:** ✅ Ready for Internet Access
**Last Updated:** 2025-10-29
