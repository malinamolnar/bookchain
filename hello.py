from cloudant import Cloudant
from cloudant.document import Document
from cloudant.query import Query
from flask import Flask, render_template, request, jsonify, redirect, url_for,g, flash, session
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
import atexit
import os
import json

app = Flask(__name__, static_url_path='')

db_name = 'mydb'
client = None
db = None
app.secret_key = os.urandom(24)

mail_settings = {
    "MAIL_SERVER": "smtp.gmail.com",
    "MAIL_PORT": 465,
    "MAIL_USE_TLS": False,
    "MAIL_USE_SSL": True,
    "MAIL_USERNAME": "bookchain.message@gmail.com",
    "MAIL_PASSWORD": "nijgzfbukjlydtns"	
	}
app.config.update(mail_settings)
mail = Mail(app)

if 'VCAP_SERVICES' in os.environ:
    vcap = json.loads(os.getenv('VCAP_SERVICES'))
    print('Found VCAP_SERVICES')
    if 'cloudantNoSQLDB' in vcap:
        creds = vcap['cloudantNoSQLDB'][0]['credentials']
        user = creds['username']
        password = creds['password']
        url = 'https://' + creds['host']
        client = Cloudant(user, password, url=url, connect=True)
        db = client.create_database(db_name, throw_on_exists=False)    
elif "CLOUDANT_URL" in os.environ:
    client = Cloudant(os.environ['CLOUDANT_USERNAME'], os.environ['CLOUDANT_PASSWORD'], url=os.environ['CLOUDANT_URL'], connect=True)
    db = client.create_database(db_name, throw_on_exists=False)
elif os.path.isfile('vcap-local.json'):
    with open('vcap-local.json') as f:
        vcap = json.load(f)
        print('Found local VCAP_SERVICES')
        creds = vcap['services']['cloudantNoSQLDB'][0]['credentials']
        user = creds['username']
        password = creds['password']
        url = 'https://' + creds['host']
        client = Cloudant(user, password, url=url, connect=True)
        db = client.create_database(db_name, throw_on_exists=False)


port = int(os.getenv('PORT', 8000))


@app.route('/')
def root():
    if client:
        my_dict = {}
        query = Query(db, selector= {'type': {'$eq': 'book'}})
        if len(query()['docs']) == 0:
            flash('error, no books found')
            return render_template('index.html')
        else:   
            for doc in query()['docs']:
                my_dict[doc['author']] =  [doc['title'], doc['_id']]
            return render_template('index.html', books=my_dict)
    else:
        flash('error, not connected to the database')
        return render_template('index.html') 

@app.route('/index')
def index():
    if client:
        my_dict = {}
        query = Query(db, selector= {'type': {'$eq': 'book'}})
        if len(query()['docs']) == 0:
            flash('error, no books found')
            return render_template('index.html')
        else:   
            for doc in query()['docs']:
                my_dict[doc['author']] =  [doc['title'], doc['_id']]
            return render_template('index.html', books=my_dict)
    else:
        flash('error, not connected to the database')
        return render_template('index.html') 


@app.route('/login', methods=['GET'])
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_post():
    session.pop('user',None)
    email = request.form.get('email')
    password = request.form.get('password')
    if client:
        query = Query(db, selector= {'email': {'$eq': email}})
        if len(query()['docs']) == 0:
            flash('Looks like you are not registered yet')
            return redirect(url_for('login'))
        else:   
            if len(query()['docs']) == 1:
                for doc in query()['docs']:
                    idd = doc['_id']
                    name = doc['name']
                    true_pass = doc['password']
                
                if check_password_hash(true_pass,password):
                    session['mail'] = email
                    session['user_id'] = doc['_id']
                    session['user'] = name
                    return redirect(url_for('index'))
                else:
                    flash('Wrong password')
                    return redirect(url_for('login'))
            else:
                flash('strange, there is more than one user with the same email')
                return redirect(url_for('login'))
    else:
        flash('error, no database')
        return redirect(url_for('login'))



@app.route('/signup', methods=['GET'])
def signup():
    return render_template('signup.html')

@app.route('/signup', methods=['POST'])
def put_signup():
    not_empty = True
    email = request.form.get('email')
    plain_password = request.form.get('password')
    name = request.form.get('name')
    books = []
    transferred_books = 0
    if email == "" or name == "" or plain_password == "":
        not_empty = False

    if client and not_empty:
        query = Query(db, selector= {'email': {'$eq': email}})
        if len(query()['docs']) == 0:   #nu exista utilizatorul
            password=generate_password_hash(plain_password, method='sha256')
            data = {'name': name, 'email':email, 'password':password, 'type':'user', 'books':books, 'transferred_books':transferred_books}
            my_document = db.create_document(data)
            flash('Account created! You can now login')
            return redirect(url_for('signup'))
        else:
            flash('Email address already exists')
            return redirect(url_for('signup'))
    else:
        if not_empty is False:
            flash('You still have something left to fill')
        return redirect(url_for('signup'))

@app.before_request
def before_request():
    g.user = None
    if 'user' in session:
        g.user = session['user']

@app.route('/logout')
def logout():
    session.pop('user',None)
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET'])
def profile():
    if g.user:
        my_dict = {}
        doc = db[session['user_id']]
        b = doc['books']
        for id_book in range(0,len(b)):
            book_doc = db[b[id_book]]
            book_name = book_doc['title']
            book_author = book_doc['author']
            my_dict[book_name] = book_author
        return render_template('profile.html', books=my_dict)
    else:
        return redirect(url_for('login'))


@app.route('/add_book', methods=['POST'])
def put_book():
    if g.user:
        title = request.form.get('title')
        author = request.form.get('author')
        current_owner = session['user_id']       #each book will have the current owner stored
        data = {'title':title, 'author':author, 'type' : 'book', 'current_owner': current_owner}
        not_empty = True
        if title == "" or author == "":
            not_empty = False
        if client and not_empty:
            my_document = db.create_document(data)    #create the document in the database
            data['_id'] = my_document['_id']
            user_with_book = db[session['user_id']]    #get the id of the logged user (stored in the session)
            user_with_book['books'].append(my_document['_id']);    #add the id of the book in the user's list
            user_with_book.save()   #save the changes in the database
            flash('Added')
            return redirect(url_for('add_book'))
        else:
            flash('You have to fill all the details...')
            return redirect(url_for('add_book'))
    else:
        return redirect(url_for('login'))   

@app.route('/add_book', methods=['GET'])
def add_book():
    if g.user:
        return render_template("add_book.html")
    else:
        return redirect(url_for('login'))


@app.route('/send_message_form', methods=['GET'])
def send_message_form():
    if g.user: 
        book_id = request.args['id']
        book_doc = db[book_id]
        current_owner = book_doc['current_owner']   #the id of the current owner
        return render_template("send_message.html", book_title=book_doc['title'], book_author=book_doc['author'], id_owner=current_owner, id_book=book_id, future_owner=session['user_id'])
    else:
        return redirect(url_for('login'))

@app.route('/send_message_form', methods = ['POST'])
def put_send_message_form():
    return redirect(url_for('index'))


@app.route('/send_message_to_owner', methods=['POST'])
def send_message_to_owner():
    if g.user:

        current_owner = request.form.get('owner')   #id
        message = request.form.get('message')
        aut = request.form.get('author')
        tit = request.form.get('title')
        id_book = request.form.get('id-book')
        future_owner = request.form.get('future-owner')

        #print("current owner:", current_owner)
        #print("id book:", id_book)
        #print("future owner", future_owner)

        logged_user_id = session['user_id']
        logged_user_email = db[logged_user_id]['email']

        email_owner = db[current_owner]['email']
        name_owner = db[current_owner]['name']

        msg = Message(subject="Someone wants to borrow your book", sender="Bookchain", recipients=[email_owner])
        msg.html=render_template('message.html', user_name= name_owner, email=logged_user_email, mess=message, title = tit, author = aut, id_b= id_book, future= future_owner, current=current_owner)
        mail.send(msg)

        flash('Sent!')
        return render_template("send_message.html", book_title=tit, book_author=aut, id_owner=current_owner, id_book=id_book, future_owner=session['user_id'])
    else:
        return redirect(url_for('login'))

@app.route('/transfer', methods=['GET'])
def transfer():
    
    if  request.args.get('id_book') is None or  request.args.get('current') is None or  request.args.get('future') is None :
        return redirect(url_for('login'))
    else:
        id_book = request.args['id_book']
        current_owner_id = request.args['current']
        future_owner_id = request.args['future']

        #getting the documents from the database
        my_book_document = db[id_book]
        future_owner_document = db[future_owner_id]
        current_owner_document = db[current_owner_id]

        if my_book_document['current_owner'] == current_owner_id:

            #changing the current user of the book
            my_book_document['current_owner'] = future_owner_id
            my_book_document.save()

            #updating the book list of the new owner
            future_list = future_owner_document['books']
            future_list.append(id_book)
            future_owner_document['books'] = future_list
            future_owner_document.save()

            #deleting the book from the old owner
            book_list = current_owner_document['books']
            book_list.remove(id_book)
            current_owner_document['books'] = book_list
            nr_transferred_books = current_owner_document['transferred_books']
            nr_transferred_books = nr_transferred_books + 1
            current_owner_document['transferred_books'] = nr_transferred_books
            current_owner_document.save()

            #print("current owner:", current_owner_id)
            #print("id book:", id_book)
            #print("future owner", future_owner_id)
            return render_template("transfer.html", message="The book has been transferred")
        else:
            return render_template("transfer.html", message="This link is not valid anymore")

@app.route('/about', methods=['GET'])
def about():
    return render_template("about.html")



@atexit.register
def shutdown():
    if client:
        client.disconnect()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)


