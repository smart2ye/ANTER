import sqlite3
import sys

def show_chat(username1, username2):
    conn = sqlite3.connect('instance/anter.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            u1.username AS from_user,
            u2.username AS to_user,
            m.content,
            m.created_at
        FROM messages m
        JOIN users u1 ON m.sender_id = u1.id
        JOIN users u2 ON m.receiver_id = u2.id
        WHERE (u1.username = ? AND u2.username = ?)
           OR (u1.username = ? AND u2.username = ?)
        ORDER BY m.created_at ASC
    """, (username1, username2, username2, username1))
    
    messages = cursor.fetchall()
    
    if not messages:
        print(f"❌ لا توجد رسائل بين {username1} و {username2}")
        return
    
    print(f"\n📱 محادثة بين {username1} و {username2}")
    print("=" * 50)
    
    for from_user, to_user, content, created_at in messages:
        if from_user == username1:
            print(f"👤 {from_user} → {to_user}: {content}")
        else:
            print(f"   {from_user} ← {to_user}: {content}")
        print(f"   🕐 {created_at}")
        print("-" * 40)
    
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("الاستخدام: python show_chat.py <username1> <username2>")
        print("مثال: python show_chat.py abdulqader.mahdly manus_ai")
    else:
        show_chat(sys.argv[1], sys.argv[2])
