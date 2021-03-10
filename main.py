from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm, EmailForm
from flask_gravatar import Gravatar
from flask_mail import Mail, Message
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 465
app.config["MAIL_USE_SSL"] = True
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD")
Bootstrap(app)
ckeditor = CKEditor(app)
login_manager = LoginManager()
login_manager.init_app(app)

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "sqlite:///blog.db")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
mail = Mail(app)

gravatar = Gravatar(
    app,
    size=100,
    rating='g',
    default='retro',
    force_default=False,
    force_lower=False,
    use_ssl=False,
    base_url=None
)


# CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = "blog_users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), nullable=False, unique=True)
    password_hash = db.Column(db.String(250), nullable=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", backref="comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('blog_users.id'))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", backref="comments")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("blog_users.id"))
    blog_post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))


db.create_all()


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():

            flash('The User with given email already exists. Please Login!')
            return redirect(url_for('login'))
        user = User(
            name=form.name.data,
            email=form.email.data,
            password_hash=generate_password_hash(form.password.data)
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        # created_user = User.query.filter_by(email=form.email.data).first()
        # print(f"{created_user.id}, "
        #       f"{created_user.email}, \n"
        #       f"{created_user.password_hash}, "
        #       f"{created_user.name}")
        return redirect(url_for('get_all_posts'))

    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        password = form.password.data
        email = form.email.data
        user = User.query.filter_by(email=email).first()
        print(user)
        if user is None:
            flash(u'Sign Up or Sign In', category='error')
            return redirect(url_for('register'))
        if check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('get_all_posts'))
        else:
            flash(u'Invalid password provided', 'error')
            return redirect(url_for('login'))

    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    form = CommentForm()
    comments = Comment.query.filter_by(blog_post_id=post_id).all()
    print(comments)
    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login to leave a comment!", 'error')
            return redirect(url_for('login'))
        comment = Comment(
            text=form.comment.data,
            blog_post_id=post_id,
            user_id=current_user.id
        )
        db.session.add(comment)
        db.session.commit()
        return redirect(url_for('show_post', post_id=post_id))
    return render_template(
        "post.html",
        post=requested_post,
        form=form,
        comments=comments
    )


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    form = EmailForm()
    if form.validate_on_submit():
        # TODO 1: Add autofill form data for user currently authenticated
        message = Message(
            f"Message from {form.email.data}",
            sender=[app.config["MAIL_USERNAME"]],
            recipients=[app.config["MAIL_USERNAME"]]
        )
        credentials = f"<p id='name'>{form.name.data}</p>\n" \
                      f"<p id='phone'>{form.phone.data}</p>\n" \
                      f"<p id='email'>{form.email.data}</p>"
        message.html = form.message.data + credentials
        mail.send(message)
        flash('Message successfully sent', 'info')
        return redirect(url_for('contact'))
        # pass
    return render_template("contact.html", form=form)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author_id = current_user.id
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(
        # host='0.0.0.0',
        port=5000,
        debug=True
    )
