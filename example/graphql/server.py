"""Simple GraphQL test server for integration testing using SQLite and strawberry-graphql"""

from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy
import strawberry
from sqlalchemy.orm import declarative_base
from strawberry.flask.views import GraphQLView
from strawberry_sqlalchemy_mapper import (
    StrawberrySQLAlchemyMapper,
    StrawberrySQLAlchemyLoader,
)

strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()

db = SQLAlchemy()

Base = declarative_base()


class models:
    """dummy module to contains models so they dont have to be a in a separate file

    requires because strawberry seems to (?) do name-based resolution of models"""
    class User(Base):
        __tablename__ = "users"

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(100), nullable=False)
        email = db.Column(db.String(100), nullable=False)

    class Post(Base):
        __tablename__ = "posts"

        id = db.Column(db.Integer, primary_key=True)
        title = db.Column(db.String(200), nullable=False)
        content = db.Column(db.Text, nullable=False)
        author_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
        # Relationship
        author = db.relationship("User", backref="posts")


@strawberry_sqlalchemy_mapper.type(models.User)
class User:
    pass


@strawberry_sqlalchemy_mapper.type(models.Post)
class Post:
    pass


@strawberry.type
class Query:
    @strawberry.field(graphql_type=User)
    def user(self, id: int) -> User | None:
        return models.User.query.get(id)

    @strawberry.field(graphql_type=list[User])
    def users(self) -> list[User]:
        return models.User.query.all()

    @strawberry.field(graphql_type=Post)
    def post(self, id: int) -> Post | None:
        return models.Post.query.get(id)

    @strawberry.field(graphql_type=list[Post])
    def posts(self) -> list[Post]:
        return models.Post.query.all()

    @strawberry.field(graphql_type=list[Post])
    def user_posts(self, author_id: int) -> list[Post]:
        return models.Post.query.filter_by(author_id=author_id).all()


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_user(self, name: str, email: str) -> User:
        user = models.User(name=name, email=email)
        db.session.add(user)
        db.session.commit()
        return user

    @strawberry.mutation
    def create_post(self, title: str, content: str, author_id: str) -> Post:
        post = models.Post(title=title, content=content, author_id=author_id)
        db.session.add(post)
        db.session.commit()
        return post


# context is expected to have an instance of StrawberrySQLAlchemyLoader
class CustomGraphQLView(GraphQLView):
    def get_context(self):
        return {
            "sqlalchemy_loader": StrawberrySQLAlchemyLoader(bind=db),
        }


strawberry_sqlalchemy_mapper.finalize()
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
)

app = Flask(__name__)
# Configure SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///test.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the database with the app
db.init_app(app)

app.add_url_rule(
    "/graphql",
    view_func=GraphQLView.as_view(
        "graphql",
        schema=schema,
        graphiql=True,  # for having the GraphiQL interface
        # Add context with the database session
        get_context=lambda: {"session": db.session},
    ),
)


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    app.run(host="localhost", port=8001, debug=True)
