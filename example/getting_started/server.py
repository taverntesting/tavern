#!/usr/bin/env python3
"""
Simple test server for Tavern getting started examples.
This server provides basic API endpoints to demonstrate Tavern testing concepts.
"""

from flask import Flask, request, jsonify
import uuid
import time

app = Flask(__name__)

# In-memory storage for demo purposes
users = {}
sessions = {}
posts = {}

@app.route('/health', methods=['GET'])
def health_check():
    """Basic health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": time.time()
    })

@app.route('/users', methods=['POST'])
def create_user():
    """Create a new user"""
    data = request.get_json()

    if not data or 'username' not in data or 'email' not in data:
        return jsonify({"error": "username and email are required"}), 400

    user_id = str(uuid.uuid4())
    users[user_id] = {
        "id": user_id,
        "username": data['username'],
        "email": data['email'],
        "created_at": time.time()
    }

    return jsonify(users[user_id]), 201

@app.route('/users/<user_id>', methods=['GET'])
def get_user(user_id):
    """Get user by ID"""
    if user_id not in users:
        return jsonify({"error": "User not found"}), 404

    return jsonify(users[user_id])

@app.route('/login', methods=['POST'])
def login():
    """Simple login endpoint"""
    data = request.get_json()

    if not data or 'username' not in data or 'password' not in data:
        return jsonify({"error": "username and password are required"}), 400

    # Simple demo - accept any username/password
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "username": data['username'],
        "created_at": time.time()
    }

    return jsonify({
        "session_id": session_id,
        "message": "Login successful"
    }), 200

@app.route('/posts', methods=['POST'])
def create_post():
    """Create a new post (requires authentication)"""
    # Check for session header
    session_id = request.headers.get('X-Session-ID')
    if not session_id or session_id not in sessions:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json()
    if not data or 'title' not in data or 'content' not in data:
        return jsonify({"error": "title and content are required"}), 400

    post_id = str(uuid.uuid4())
    posts[post_id] = {
        "id": post_id,
        "title": data['title'],
        "content": data['content'],
        "author": sessions[session_id]['username'],
        "created_at": time.time()
    }

    return jsonify(posts[post_id]), 201

@app.route('/posts/<post_id>', methods=['GET'])
def get_post(post_id):
    """Get post by ID"""
    if post_id not in posts:
        return jsonify({"error": "Post not found"}), 404

    return jsonify(posts[post_id])

@app.route('/posts', methods=['GET'])
def list_posts():
    """List all posts"""
    return jsonify({
        "posts": list(posts.values()),
        "count": len(posts)
    })

@app.route('/error/demo', methods=['GET'])
def error_demo():
    """Demo endpoint that returns different error codes"""
    error_type = request.args.get('type', 'not_found')

    if error_type == 'not_found':
        return jsonify({"error": "Resource not found"}), 404
    elif error_type == 'unauthorized':
        return jsonify({"error": "Unauthorized"}), 401
    elif error_type == 'server_error':
        return jsonify({"error": "Internal server error"}), 500
    else:
        return jsonify({"error": "Bad request"}), 400

@app.route('/slow', methods=['GET'])
def slow_endpoint():
    """Endpoint that takes time to respond"""
    import time
    time.sleep(2)  # Simulate slow response
    return jsonify({"message": "Slow response completed"})

if __name__ == '__main__':
    print("Starting Tavern Getting Started Test Server...")
    print("Server will be available at: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    app.run(debug=True, host='0.0.0.0', port=5000)
