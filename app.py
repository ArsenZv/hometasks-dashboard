from flask import Flask, render_template, request, jsonify
import json

app = Flask(__name__)

DATA_FILE = 'data.json'

def load_data():
    try:
        with open(DATA_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return []

def save_data(data):
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4)

@app.route('/')
def index():
    items = load_data()
    return render_template('index.html', items=items)

@app.route('/add', methods=['POST'])
def add_item():
    data = load_data()
    new_item = request.json.get('item')
    if new_item:
        data.append(new_item)
        save_data(data)
        return jsonify({'success': True, 'items': data})
    return jsonify({'success': False}), 400

if __name__ == '__main__':
    app.run(debug=True)