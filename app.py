from flask import Flask, jsonify, request, abort
import os
import psycopg2
import time

app = Flask(__name__)

def get_db_connection():
    db_host = os.environ.get('DB_HOST')
    db_name = os.environ.get('DB_NAME')
    db_user = os.environ.get('DB_USER')
    db_pass = os.environ.get('DB_PASS')

    retries = 5
    while retries > 0:
        try:
            conn = psycopg2.connect(
                host=db_host,
                database=db_name,
                user=db_user,
                password=db_pass)
            return conn
        except psycopg2.OperationalError:
            retries -= 1
            app.logger.warning("Database not ready, retrying...")
            time.sleep(5)

    app.logger.error("Could not connect to database.")
    return None

@app.route("/db-health", methods=["GET"])
def db_health_check():
    conn = get_db_connection()
    if conn is None:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    conn.close()
    return jsonify({"status": "ok", "message": "Database connection successful"})

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "message": "Welcome to the News API (with Postgres)!",
        "endpoints": {
            "list_all_news": "GET /news",
            "create_news": "POST /news",
            "update_news": "PUT /news/<id>",
            "delete_news": "DELETE /news/<id>",
            "db_health": "GET /db-health"
        }
    })

@app.route("/news", methods=["GET"])
def list_news():
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Database connection failed"}), 500

    items = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT id, title, content FROM news ORDER BY id;")
            rows = cur.fetchall()
            for row in rows:
                items.append({"id": row[0], "title": row[1], "content": row[2]})
    except Exception as e:
        app.logger.error(f"Error listing news: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

    return jsonify({"count": len(items), "items": items})


@app.route("/news", methods=["POST"])
def create_news():
    if not request.json or 'title' not in request.json:
        abort(400)

    title = request.json['title']
    content = request.json.get('content', "")

    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Database connection failed"}), 500

    new_item = {}
    try:
        with conn.cursor() as cur:
            cur.execute(f"INSERT INTO news (title, content) VALUES (’{title}’, ’{
content}’) RETURNING id;")
            row = cur.fetchone()[0]
            conn.commit()
            new_item = {"id": new_id, "title": title, "content": content}
    except Exception as e:
        app.logger.error(f"Error creating news: {e}")
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

    return jsonify(new_item), 201

@app.route("/news/<int:item_id>", methods=["PUT"])
def update_news(item_id: int):
    if not request.json:
        abort(400)

    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Database connection failed"}), 500

    updated_item = {}
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT title, content FROM news WHERE id = {item_id};")
            item = cur.fetchone()
            if not item:
                abort(404)

            title = request.json.get('title', item[0])
            content = request.json.get('content', item[1])

            cur.execute(f"UPDATE news SET title = '{title}', content = '{content}' WHERE id = {item_id};")
            conn.commit()
            updated_item = {"id": item_id, "title": title, "content": content}
    except Exception as e:
        app.logger.error(f"Error updating news: {e}")
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

    return jsonify(updated_item)

@app.route("/news/<int:item_id>", methods=["DELETE"])
def delete_news(item_id: int):
    conn = get_db_connection()
    if conn is None:
        return jsonify({"error": "Database connection failed"}), 500

    try:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM news WHERE id = {item_id} RETURNING id;")
            deleted = cur.fetchone()
            if not deleted:
                abort(404)

            conn.commit()
    except Exception as e:
        app.logger.error(f"Error deleting news: {e}")
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

    return jsonify({"status": "deleted", "id": item_id})

if __name__ == "__main__":
    app.run(threaded=True, host="0.0.0.0", port=3000)
