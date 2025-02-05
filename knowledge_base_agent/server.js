const express = require('express');
const { exec } = require('child_process');
const http = require('http');
const socketIo = require('socket.io');
const fs = require('fs');
const path = require('path');

const app = express();
const server = http.createServer(app);
const io = socketIo(server);

const BOOKMARKS_FILE = path.join(__dirname, 'data', 'bookmarks_links.txt');

app.use(express.static('public')); // Serve frontend files

// WebSocket for real-time updates
io.on('connection', (socket) => {
  console.log('Client connected');
  socket.on('disconnect', () => console.log('Client disconnected'));
});

// Function to run a script and stream logs
function runScript(command, eventName) {
  const process = exec(command);

  process.stdout.on('data', (data) => {
    console.log(data);
    io.emit(eventName, data.toString());
  });

  process.stderr.on('data', (data) => {
    console.error(data);
    io.emit(eventName, `ERROR: ${data.toString()}`);
  });

  process.on('close', (code) => {
    io.emit(eventName, `Process exited with code ${code}`);
    if (code === 0) io.emit(eventName, 'Completed successfully.');
  });
} // **← This closing bracket was missing!**

/* API Routes */

// API to start the scraper
app.get('/start-scraper', (req, res) => {
  runScript('node scrape_x_bookmarks.js', 'scraper-log');
  res.json({ message: 'Scraper started' });
});

// API to fetch bookmarks file content
app.get('/bookmarks', (req, res) => {
  if (fs.existsSync(BOOKMARKS_FILE)) {
    res.sendFile(BOOKMARKS_FILE);
  } else {
    res.status(404).json({ error: 'No bookmarks found' });
  }
});

// API to start AI-Agent processing
app.get('/start-ai-agent', (req, res) => {
  runScript('python3 ai-agent.py', 'ai-agent-log');
  res.json({ message: 'AI Agent started' });
});

const PORT = 5000;
server.listen(PORT, () => console.log(`Server running on http://localhost:${PORT}`));
