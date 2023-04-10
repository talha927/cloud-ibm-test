"""
Helper script for running flask server and perform DB migrations
"""
import os

from flask_migrate import Migrate

from ibm import models
from ibm.web import create_app, db

app = create_app(os.getenv('FLASK_CONFIG') or 'default')
migrate = Migrate(app, db)


@app.shell_context_processor
def make_shell_context():
    return dict(app=app, db=db, models=models)


@app.cli.command()
def pre_reqs():
    pass


@app.cli.command()
def deploy():
    """Run deployment tasks."""
    from flask_migrate import upgrade

    # migrate database to latest revision
    upgrade()


if __name__ == "__main__":
    app.run()
