from confluent_kafka import Consumer, KafkaError
import json
import logging
from threading import Thread
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Callable
import os
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class KafkaConsumer:
    def __init__(self, db_session_getter: Callable[[], Session]):
        bootstrap_servers = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        group_id = os.getenv('KAFKA_GROUP_ID', 'fastapi-user-sync-consumer')
        topic = os.getenv('KAFKA_TOPIC', 'tinode.account-events')

        logger.info(f"Kafka configuration:")
        logger.info(f"  Bootstrap servers: {bootstrap_servers}")
        logger.info(f"  Group ID: {group_id}")
        logger.info(f"  Topic: {topic}")

        self.config = {
            'bootstrap.servers': bootstrap_servers,
            'group.id': group_id,
            'auto.offset.reset': 'earliest',
            'enable.auto.commit': True,
            'session.timeout.ms': 6000,
            'max.poll.interval.ms': 300000,
        }
        self.consumer = Consumer(self.config)
        self.db_session_getter = db_session_getter
        self.running = False
        self.thread = None
        self.topic = topic

    def start(self):
        """Запуск потребителя в отдельном потоке"""
        try:
            self.consumer.subscribe([self.topic])
            self.running = True
            self.thread = Thread(target=self._consume_loop, daemon=True, name="KafkaConsumer")
            self.thread.start()
            logger.info(f"Kafka consumer started for topic '{self.topic}'")
            logger.info(f"Connecting to: {self.config['bootstrap.servers']}")
        except Exception as e:
            logger.error(f"Failed to start Kafka consumer: {e}")
            self.running = False

    def stop(self):
        """Остановка потребителя"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.consumer.close()
        logging.info("Kafka consumer stopped")

    def _consume_loop(self):
        """Основной цикл потребления сообщений"""
        while self.running:
            try:
                msg = self.consumer.poll(timeout=1.0)
                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logging.error(f"Kafka error: {msg.error()}")
                    continue
                self._process_message(msg.value())
                self.consumer.commit(msg)
            except Exception as e:
                logging.error(f"Error in consumer loop: {e}")

    def _process_message(self, message_bytes: bytes):
        """Обработка сообщения из Kafka"""
        try:
            message = json.loads(message_bytes.decode('utf-8'))
            event_type = message.get('event_type')
            user_data = message.get('data', {})
            source = message.get('source', '')
            if source == 'fastapi-user-service':
                logging.debug(f"Skipping self-generated event: {event_type}")
                return
            db = self.db_session_getter()
            try:
                if event_type == 'account_created':
                    self._handle_account_created(db, user_data)
                elif event_type == 'account_updated':
                    self._handle_account_updated(db, user_data)
                elif event_type == 'account_deleted':
                    self._handle_account_deleted(db, user_data)
                else:
                    logging.warning(f"Unknown event type: {event_type}")
                db.commit()
            except Exception as e:
                db.rollback()
                logging.error(f"Database error processing {event_type}: {e}")
            finally:
                db.close()

        except json.JSONDecodeError as e:
            logging.error(f"Invalid JSON: {e}")
        except Exception as e:
            logging.error(f"Error processing message: {e}")

    def _handle_account_created(self, db: Session, user_data: dict):
        """Создание пользователя из события Kafka (только если его нет)"""
        from models.user import UserDB, UserRole
        user_id = user_data.get('user_id')
        username = user_data.get('username')
        if not user_id or not username:
            logging.error("Missing user_id or username in create event")
            return
        existing = db.query(UserDB).filter(UserDB.id == user_id).first()
        if existing:
            logging.debug(f"User {user_id} already exists, skipping create")
            return
        existing_by_name = db.query(UserDB).filter(UserDB.username == username).first()
        if existing_by_name:
            logging.warning(f"Username {username} exists with different ID, updating ID")
            existing_by_name.id = user_id
            return
        new_user = UserDB(
            id=user_id,
            username=username,
            full_name=user_data.get('full_name', ''),
            role=UserRole(user_data.get('role', 'user')),
            created_at=datetime.fromisoformat(user_data['created_at'])
            if 'created_at' in user_data else datetime.utcnow()
        )
        db.add(new_user)
        logging.info(f"Created user from Kafka: {username} (ID: {user_id})")

    def _handle_account_updated(self, db: Session, user_data: dict):
        """Обновление пользователя из события Kafka"""
        from models.user import UserDB, UserRole
        user_id = user_data.get('user_id')
        if not user_id:
            logging.error("No user_id in update event")
            return
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            logging.warning(f"User {user_id} not found for update, creating")
            self._handle_account_created(db, user_data)
            return
        if 'username' in user_data:
            user.username = user_data['username']
        if 'full_name' in user_data:
            user.full_name = user_data['full_name']
        if 'role' in user_data:
            try:
                user.role = UserRole(user_data['role'])
            except ValueError:
                logging.warning(f"Invalid role value: {user_data['role']}")

        logging.info(f"Updated user from Kafka: {user.username}")

    def _handle_account_deleted(self, db: Session, user_data: dict):
        """Удаление пользователя из события Kafka"""
        from models.user import UserDB
        user_id = user_data.get('user_id')
        if not user_id:
            logging.error("No user_id in delete event")
            return
        user = db.query(UserDB).filter(UserDB.id == user_id).first()
        if not user:
            logging.warning(f"User {user_id} not found for deletion")
            return
        db.delete(user)
        logging.info(f"Deleted user from Kafka: {user.username} (ID: {user_id})")