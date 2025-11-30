"""Simple GraphQL test server for integration testing using SQLite and strawberry-graphql with subscriptions"""

import asyncio
import logging
from collections.abc import AsyncGenerator

import strawberry
import uvicorn
from fastapi import FastAPI
from sqlalchemy import Column, ForeignKey, Integer, String, create_engine, select
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from strawberry.fastapi import GraphQLRouter
from strawberry_sqlalchemy_mapper import StrawberrySQLAlchemyMapper

strawberry_sqlalchemy_mapper = StrawberrySQLAlchemyMapper()

Base = declarative_base()


class models:
    """dummy module to contains models so they dont have to be a in a separate file"""

    class User(Base):
        __tablename__ = "users"

        id = Column(Integer, primary_key=True)
        name = Column(String(100), nullable=False)
        email = Column(String(100), nullable=False)

    class Post(Base):
        __tablename__ = "posts"

        id = Column(Integer, primary_key=True)
        title = Column(String(200), nullable=False)
        content = Column(String, nullable=False)
        author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
        author = relationship("User", backref="posts")


@strawberry_sqlalchemy_mapper.type(models.User)
class User:
    pass


@strawberry_sqlalchemy_mapper.type(models.Post)
class Post:
    pass


@strawberry.type
class Query:
    @strawberry.field
    def user(self, id: strawberry.ID) -> User:
        user = global_db_session.get(models.User, int(id))
        if user is None:
            raise Exception("User not found")
        return user

    @strawberry.field
    def users(self) -> list[User]:
        return global_db_session.execute(select(models.User)).scalars().all()

    @strawberry.field
    def post(self, id: strawberry.ID) -> Post:
        post = global_db_session.get(models.Post, int(id))
        if post is None:
            raise Exception("Post not found")
        return post

    @strawberry.field
    def posts(self) -> list[Post]:
        return global_db_session.execute(select(models.Post)).scalars().all()

    @strawberry.field
    def user_posts(self, author_id: strawberry.ID) -> list[Post]:
        posts_by_author = list(global_db_session.execute(select(models.Post).filter_by(author_id=int(author_id))).scalars().all())
        if not posts_by_author:
            raise Exception("No p")
        return posts_by_author


@strawberry.type
class Mutation:
    @strawberry.mutation
    def create_user(self, name: str, email: str, info: strawberry.Info) -> User:
        user = models.User(name=name, email=email)
        global_db_session.add(user)
        global_db_session.commit()
        info.context["background_tasks"].add_task(user_updated, user)
        return user

    @strawberry.mutation
    def create_post(
        self, title: str, content: str, author_id: str, info: strawberry.Info
    ) -> Post:
        post = models.Post(title=title, content=content, author_id=int(author_id))
        global_db_session.add(post)
        global_db_session.commit()
        return post

    @strawberry.mutation
    def update_user(
        self, id: strawberry.ID, name: str, email: str, info: strawberry.Info
    ) -> User:
        user = global_db_session.get(models.User, int(id))
        if user is None:
            raise Exception("User not found")
        user.name = name
        user.email = email
        global_db_session.commit()
        info.context["background_tasks"].add_task(user_updated, user)
        return user


q = asyncio.Queue()


async def user_updated(name: str):
    await q.put(name)


@strawberry.type
class Subscription:
    @strawberry.subscription(graphql_type=User)
    async def user(self, id: strawberry.ID) -> AsyncGenerator[User, None]:
        while True:
            user = await q.get()
            if user.id != int(id):
                continue
            logging.info(f"User {user.name} updated")
            yield user


strawberry_sqlalchemy_mapper.finalize()
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)


async def lifespan(_):
    logging.basicConfig(level=logging.INFO)
    yield


app = FastAPI(title="GraphQL Test Server", lifespan=lifespan)
app.include_router(GraphQLRouter(schema), prefix="/graphql")


@app.get("/health")
async def health():
    return {"status": "healthy"}


# DB setup
engine = create_engine("sqlite:////tmp/test.db", echo=False)
Session = sessionmaker(bind=engine)
global_db_session = Session()
Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5010,
        log_level="info",
    )
