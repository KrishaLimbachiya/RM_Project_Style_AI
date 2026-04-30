# StyleAI - Wardrobe Management App

A web-based wardrobe management application with AI-powered outfit recommendations, built with Python and HTML.

## Features

- **User Authentication**: Register and login functionality with session management
- **Wardrobe Management**: Add, view, and organize wardrobe items
- **AI Outfit Recommendations**: Get personalized outfit suggestions using Groq AI based on occasion and weather
- **Outfit History**: Track and log outfits you've worn
- **Statistics**: View wardrobe usage statistics and trends
- **Weather Integration**: Weather-aware outfit suggestions
- **Packing Assistant**: AI-powered packing recommendations for trips

## Installation

1. Clone or download the project files to your local machine.

2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables:
   - Create a `.env` file in the project root
   - Add your Groq API key(s):
     ```
     GROQ_API_KEY=your_groq_api_key_here
     GROQ_API_KEY_2=your_second_groq_api_key_here  # Optional
     ```
   - Get API keys from [Groq Console](https://console.groq.com/)

## Usage

1. Start the server:
   ```bash
   python server.py
   ```

2. Open your web browser and navigate to:
   ```
   http://localhost:3004
   ```

3. Register a new account or login with existing credentials.

4. Access different features through the navigation tabs in the main app.

## Project Structure

- `server.py` - Main Python HTTP server with API endpoints
- `login.html` - User authentication page
- `wardrobe-final (1).html` - Main wardrobe management interface
- `stats.html` - Statistics and analytics page
- `weather.html` - Weather information page
- `packing.html` - Packing assistant page
- `users.json` - User account data
- `wardrobe_*.json` - Individual user wardrobe data
- `history_*.json` - User outfit history logs
- `requirements.txt` - Python dependencies
- `.env` - Environment variables (API keys)

## API Endpoints

- `GET /` - Main app page
- `GET /login` - Login page
- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `GET /api/wardrobe` - Get user's wardrobe
- `POST /api/wardrobe` - Save wardrobe items
- `POST /api/recommend` - AI outfit recommendations
- `GET /api/history` - Get outfit history
- `POST /api/history` - Log new outfit
- `POST /api/history/delete` - Delete history entry

## Requirements

- Python 3.6+
- Groq API account for AI features
- Modern web browser

## Troubleshooting

- **AI features not working**: Ensure `GROQ_API_KEY` is set in `.env`
- **Port already in use**: Change the `PORT` variable in `server.py`
- **Permission errors**: Run the server with appropriate permissions

## License

This project is for personal use. Please respect API usage limits and terms of service.