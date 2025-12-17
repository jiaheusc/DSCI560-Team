# Group Chat + LLM Bot

This project is a group chat application that integrates a language model bot for enhanced interaction. Users can create accounts, log in, fill out a questionnaire, select chat groups, and engage in real-time messaging.

## Project Structure

```
groupchat-react-app
├── public
│   └── index.html          # Main HTML file for the React application
├── src
│   ├── index.jsx          # Entry point of the React application
│   ├── App.jsx            # Main application component
│   ├── api.js             # API calls for user authentication and group management
│   ├── ws.js              # WebSocket management for real-time messaging
│   ├── components         # Contains all React components
│   │   ├── Auth.jsx       # User authentication component
│   │   ├── Questionnaire.jsx # Questionnaire component
│   │   ├── GroupSelect.jsx # Group selection component
│   │   ├── Chat.jsx       # Chat interface component
│   │   └── Message.jsx     # Individual message display component
│   ├── hooks              # Custom hooks
│   │   └── useAuth.js     # Authentication state management hook
│   └── styles.css         # Styles for the application
├── package.json           # npm configuration file
├── .gitignore             # Files and directories to ignore by Git
└── README.md              # Project documentation
```

## Setup Instructions

1. **Clone the repository:**
   ```
   git clone <repository-url>
   cd groupchat-react-app
   ```

2. **Install dependencies:**
   ```
   npm install
   ```

3. **Run the application:**
   ```
   npm start
   ```

4. **Open your browser and navigate to:**
   ```
   http://localhost:3000
   ```

## Usage

- **Authentication:** Users can sign up or log in to access the chat features.
- **Questionnaire:** New users must fill out a questionnaire before joining a group.
- **Group Selection:** Users can select an existing group or create a new one.
- **Chat Interface:** Engage in real-time messaging with other users in the selected group.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License.