# Queue Management System

A web-based queue management system with QR code generation for individual queue tracking.

## Features

- 🎫 Generate unique queue numbers
- 📱 QR code generation for easy access
- 🔍 Individual queue status tracking
- 🖥️ Clean kiosk-style interface
- 🗄️ PostgreSQL database storage
- 🌐 Universal access via any device

## Setup Instructions

### Prerequisites

- Python 3.7+
- PostgreSQL database
- Modern web browser

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Engr-Carlo/Queue-Management-System.git
   cd Queue-Management-System
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up PostgreSQL database**
   - Create a database named `queue_system`
   - Create the queue table:
   ```sql
   CREATE TABLE queue (
       id VARCHAR(255) PRIMARY KEY,
       number VARCHAR(50) NOT NULL,
       person VARCHAR(255) NOT NULL,
       date VARCHAR(100) NOT NULL,
       time VARCHAR(50) NOT NULL,
       status VARCHAR(50) NOT NULL
   );
   ```

4. **Configure environment variables**
   - Copy `.env.example` to `.env`
   - Update the database credentials in `.env`:
   ```
   DB_NAME=queue_system
   DB_USER=your_username
   DB_PASSWORD=your_password
   DB_HOST=localhost
   DB_PORT=5432
   ```

5. **Run the backend server**
   ```bash
   python backend.py
   ```

6. **Open the frontend**
   - Open `index.html` or `Home.html` in your web browser
   - Or serve it using a local web server

## Usage

1. **Generate Queue Number**
   - Select the person you want to visit
   - Click "Next" to generate your queue number
   - Scan the QR code or save the link for status tracking

2. **Check Queue Status**
   - Use the QR code or direct link to check your position
   - Real-time updates on estimated wait time

## API Endpoints

- `POST /queue` - Create new queue entry
- `GET /queue/<id>` - Get queue status by ID
- `GET /test-db` - Test database connection

## File Structure

```
├── backend.py              # Flask API server
├── index.html             # Main landing page
├── Home.html              # Queue generation page
├── queue-number.html      # Queue number display
├── queue-status.html      # Queue status tracking
├── style.css              # Styles
├── images/                # Logo images
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
└── README.md             # This file
```

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is open source and available under the [MIT License](LICENSE).
