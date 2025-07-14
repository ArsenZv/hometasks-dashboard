# HomeTasks Dashboard

## Overview
HomeTasks Dashboard is a web application designed to help users manage their daily tasks effectively. It provides features such as task tracking, lifespan management, and dynamic updates.

## Features
- Add new tasks with a specified lifespan.
- Refresh tasks to reset their lifespan.
- Visual indicators (color-coded) for task status based on time elapsed.
- Dynamic display of today's date.

## Development Setup Instructions
1. Clone the repository:
   ```bash
   git clone <repository-url>
   ```
2. Navigate to the project directory:
   ```bash
   cd hometasks-dashboard
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   python app.py
   ```
5. Open the application in your browser at `http://localhost:5555`.

## Using Docker-Compose

To run the application in a container using Docker-Compose:

1. Ensure Docker and Docker-Compose are installed on your system.
2. Use the existing `docker-compose.yml` file located in the project directory.
3. Build and start the container:
   ```bash
   docker-compose up 
   ```
   optionally
   ```bash
   docker-compose up --build
   ```
4. Access the application at `http://localhost:5555` in your browser.

## Usage
- Add tasks using the input fields and "Add" button.
- Refresh tasks by clicking the refresh icon next to each task.
- View task status with color-coded indicators:
  - **Green**: Task is fresh.
  - **Yellow**: Task is halfway through its lifespan.
  - **Red**: Task has expired.

## File Structure
- `static/`: Contains JavaScript and CSS files.
- `templates/`: Contains HTML templates.
- `app.py`: Main application file.
- `data/`: Stores task data in JSON format.

## License
This project is licensed under the MIT License.