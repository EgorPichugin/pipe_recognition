from fastapi import FastAPI

from src.routers.report_router import router as report_generation_router


def create_app():
    app = FastAPI(title="Hackathon Vienna")
    app.include_router(report_generation_router)
    return app
