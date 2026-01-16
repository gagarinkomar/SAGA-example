import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models import SagaStep as SagaStepModel

logger = logging.getLogger(__name__)


class SagaStepBase(ABC):
    def __init__(self, db: Session, order_id: int):
        self.db = db
        self.order_id = order_id

    @abstractmethod
    def execute(self) -> None:
        pass

    @abstractmethod
    def compensate(self) -> None:
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass

    def run(self) -> None:
        step_name = self.get_name()
        logger.info(f"Executing step: {step_name}")
        
        step = SagaStepModel(
            order_id=self.order_id,
            step_name=step_name,
            status="STARTED",
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(step)
        self.db.commit()

        try:
            self.execute()
            step.status = "COMPLETED"
            step.finished_at = datetime.now(timezone.utc)
            self.db.commit()
            logger.info(f"Step {step_name} completed")
        except Exception as e:
            self.db.rollback()
            step.status = "FAILED"
            step.error = str(e)
            step.finished_at = datetime.now(timezone.utc)
            self.db.commit()
            logger.error(f"Step {step_name} failed: {e}")
            raise

    def run_compensation(self) -> None:
        step_name = self.get_name()
        try:
            logger.info(f"Compensating step: {step_name}")
            self.compensate()
            comp_step = SagaStepModel(
                order_id=self.order_id, step_name=f"Compensate_{step_name}",
                status="COMPLETED",
                started_at=datetime.now(timezone.utc),
                finished_at=datetime.now(timezone.utc),
            )
            self.db.add(comp_step)
            self.db.commit()
            logger.info(f"Compensation for {step_name} completed")
        except Exception as e:
            self.db.rollback()
            logger.error(f"Compensation for {step_name} failed: {e}")
