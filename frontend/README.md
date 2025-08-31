# G-SIA Frontend

A clean, modern web interface for the GovAI Secure Intelligence Assistant (G-SIA) that provides a chat-based interface for querying patient data with compliance-aware AI.

## Features

### 🎨 **Modern UI/UX**
- Clean, minimalist design with glassmorphism effects
- Responsive layout that works on desktop and mobile
- Smooth animations and transitions
- Professional color scheme with compliance-focused visual indicators

### 💬 **Chat Interface**
- Real-time chat with AI assistant
- Support for natural language queries
- Auto-expanding text input with character count
- Message history with user and AI avatars
- Loading states and error handling

### 🛡️ **Compliance Visualization**
- Clear compliance status indicators (ALLOWED/REWRITTEN/BLOCKED)
- Color-coded badges for quick status recognition
- Policy reasoning display for blocked queries
- Query modification explanations for rewritten queries

### 📊 **System Monitoring**
- Real-time system health status
- Database connection monitoring
- AI agent status tracking
- Compliance statistics dashboard
- Recent query history

### 🔧 **Technical Features**
- RESTful API integration with FastAPI backend
- Automatic status monitoring and health checks
- Toast notifications for user feedback
- Responsive design with mobile-first approach
- Modern JavaScript ES6+ with class-based architecture

## File Structure

```
frontend/
├── index.html          # Main HTML structure
├── styles.css          # CSS styling and responsive design
├── script.js           # JavaScript functionality and API integration
└── README.md           # This documentation
```

## Getting Started

### Prerequisites
- G-SIA FastAPI backend running on `http://localhost:8000`
- Modern web browser with ES6+ support
- No build tools required - pure HTML/CSS/JS

### Quick Start

1. **Start the G-SIA Backend**
   ```bash
   cd /path/to/your/g-sia/project
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Open the Frontend**
   - Simply open `frontend/index.html` in your web browser
   - Or serve it using a local HTTP server:
   ```bash
   cd frontend
   python -m http.server 8080
   # Then open http://localhost:8080
   ```

3. **Start Chatting**
   - The interface will automatically connect to the backend
   - Try asking questions about patient data
   - Watch the compliance system in action

## Usage Guide

### Making Queries

1. **Type your question** in the chat input at the bottom
2. **Press Enter** or click the send button
3. **Wait for processing** - the AI will analyze compliance
4. **View results** with compliance status and data

### Example Queries

- **"How many patients have diabetes?"** - Should be ALLOWED
- **"Show me patient names"** - Should be BLOCKED (PII violation)
- **"List patients by age"** - Should be REWRITTEN to aggregated format

### Understanding Responses

- **🟢 ALLOWED**: Query processed successfully, results displayed
- **🟡 REWRITTEN**: Query modified for compliance, explanation provided
- **🔴 BLOCKED**: Query blocked due to policy violation, reason given

## API Integration

The frontend integrates with the following G-SIA API endpoints:

- `GET /api/v1/health` - System health check
- `POST /api/v1/query` - Process user queries
- `GET /api/v1/status/metrics` - System metrics and compliance stats

### Configuration

To change the API endpoint, modify the `apiBaseUrl` in `script.js`:

```javascript
this.apiBaseUrl = 'http://your-backend-url:port/api/v1';
```

## Customization

### Styling
- Modify `styles.css` to change colors, fonts, and layout
- The design uses CSS custom properties for easy theming
- Glassmorphism effects can be adjusted in the CSS

### Functionality
- Extend `script.js` to add new features
- Modify the message formatting functions for different response types
- Add new status monitoring capabilities

### Branding
- Update the logo and title in `index.html`
- Change the color scheme in `styles.css`
- Modify the welcome message and example queries

## Browser Support

- **Chrome/Edge**: 90+ (Full support)
- **Firefox**: 88+ (Full support)
- **Safari**: 14+ (Full support)
- **Mobile browsers**: iOS Safari 14+, Chrome Mobile 90+

## Development

### Adding New Features

1. **UI Components**: Add HTML structure in `index.html`
2. **Styling**: Add CSS rules in `styles.css`
3. **Functionality**: Extend the `GSIAFrontend` class in `script.js`

### Testing

- Test on different screen sizes using browser dev tools
- Verify API integration with backend
- Check compliance status display accuracy

### Performance

- The frontend is lightweight and loads quickly
- No external dependencies except Font Awesome icons
- Efficient DOM manipulation and event handling

## Troubleshooting

### Common Issues

1. **"Could not connect to G-SIA system"**
   - Ensure the backend is running on port 8000
   - Check CORS settings in the backend
   - Verify network connectivity

2. **Queries not processing**
   - Check browser console for errors
   - Verify API endpoint configuration
   - Ensure backend services are healthy

3. **Styling issues**
   - Clear browser cache
   - Check CSS file loading
   - Verify Font Awesome CDN access

### Debug Mode

Enable debug logging by opening browser console and running:
```javascript
localStorage.setItem('debug', 'true');
```

## Future Enhancements

- **Authentication**: User login and session management
- **Query History**: Persistent chat history storage
- **Export**: Download query results as CSV/PDF
- **Advanced Analytics**: Enhanced compliance reporting
- **Real-time Updates**: WebSocket integration for live updates
- **Multi-language Support**: Internationalization (i18n)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This frontend is part of the G-SIA project and follows the same licensing terms.

## Support

For issues and questions:
- Check the troubleshooting section above
- Review the backend API documentation
- Open an issue in the project repository