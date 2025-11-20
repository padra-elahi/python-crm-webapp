from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Float, Date
from sqlalchemy.orm import relationship, Session
from datetime import datetime, date
from database import Base
from passlib.hash import bcrypt
from sqlmodel import SQLModel, Field
from typing import Optional


# --- User Model ---
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    role = Column(String)
    section = Column(String, nullable=True) 

# --- Project Model ---
class Project(Base):
    __tablename__ = 'projects'
    id = Column(Integer, primary_key=True, index=True)
    internal_number = Column(String, unique=True, index=True)
    customer = Column(String, index=True)
    request_number = Column(String, nullable=True)
    notification_date = Column(Date, nullable=True)
    delivery_date = Column(Date, nullable=True)
    description = Column(Text, nullable=False)
    weight_kg = Column(Float, nullable=True)
    expert = Column(String, nullable=True)
    operator = Column(String, nullable=True)
    warranty_pp = Column(String, nullable=True)
    tech_office_status = Column(String, nullable=True)
    purchasing_status = Column(String, nullable=True)
    production_status = Column(String, nullable=True)
    inspection_status = Column(String, nullable=True)
    shipment_date = Column(Date, nullable=True)
    invoice_date = Column(Date, nullable=True)
    payment_amount = Column(Float, nullable=True)
    payment_date = Column(Date, nullable=True)
    status = Column(String, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    tasks = relationship("Task", back_populates="project")

# --- Task Model ---
class Task(Base):
    __tablename__ = 'tasks'
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    task_type = Column(String, default='Project')
    level = Column(String, default='Normal')
    
    # Relationships
    assigned_to = Column(Integer, ForeignKey('users.id'))
    assigned_by = Column(Integer, ForeignKey('users.id'))
    leader_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)
    
    user = relationship("User", foreign_keys=[assigned_to], backref="assigned_tasks")
    admin = relationship("User", foreign_keys=[assigned_by])
    leader = relationship("User", foreign_keys=[leader_id])
    project = relationship("Project", back_populates="tasks")

    status = Column(String, default='To Do', nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    
    follow_up_date = Column(Date, nullable=True)
    follow_up_message = Column(Text, nullable=True)
    
    success_percent = Column(Float, default=0.0)
    admin_comment = Column(Text, nullable=True)
    user_comment = Column(Text, nullable=True)

    @property
    def is_failed(self):
        return self.end_date and self.end_date < date.today() and self.status != 'Completed'

# --- Notification Model ---
class Notification(Base):
    __tablename__ = 'notifications'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    task_id = Column(Integer, ForeignKey('tasks.id'), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", backref="notifications")
    task = relationship("Task")

class Customer(Base):
    __tablename__ = 'customers'
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    short_name = Column(String)
    product_type = Column(String)
    other_product_description = Column(String, nullable=True)
    product_description = Column(Text)
    website_url = Column(String)
    registration_status = Column(String)
    portal_username = Column(String)
    portal_password = Column(String)
    last_action_description = Column(Text)
    inquiry_portal = Column(String)
    address1 = Column(String)
    address2 = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    portal_username = Column(String, nullable=True)
    portal_password = Column(String, nullable=True)
    # units = relationship('CustomerUnit', back_populates='customer', cascade="all, delete-orphan")


# class CustomerUnit(Base):
#     __tablename__ = 'customer_units'
#     id = Column(Integer, primary_key=True)
#     customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
#     unit_number = Column(Integer)
#     manager = Column(String)
#     boss = Column(String)
#     supervisor = Column(String)

#     customer = relationship('Customer', back_populates='units')
#     experts = relationship('CustomerUnitExpert', back_populates='unit', cascade="all, delete-orphan")


# class CustomerUnitExpert(Base):
#     __tablename__ = 'customer_unit_experts'
#     id = Column(Integer, primary_key=True)
#     unit_id = Column(Integer, ForeignKey('customer_units.id'), nullable=False)
#     name = Column(String)

#     unit = relationship('CustomerUnit', back_populates='experts')

class CustomerUnit(Base):
    __tablename__ = 'customer_units'
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customers.id'))
    unit_number = Column(String)
    boss_name = Column(String)
    admin_name = Column(String)
    watcher_name = Column(String)

    customer = relationship("Customer", back_populates="units")
    workers = relationship("CustomerWorker", back_populates="unit", cascade="all, delete-orphan")


class CustomerWorker(Base):
    __tablename__ = 'customer_workers'
    id = Column(Integer, primary_key=True)
    unit_id = Column(Integer, ForeignKey('customer_units.id'))
    name = Column(String)

    unit = relationship("CustomerUnit", back_populates="workers")


# Add this line to Customer model:
Customer.units = relationship("CustomerUnit", back_populates="customer", cascade="all, delete-orphan")


# --- Helper Functions ---

def update_user_profile(db: Session, user_id: int, updates: dict):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    
    if 'password' in updates:
        new_password = updates.pop('password')
        if new_password:
            hashed_password = bcrypt.hash(new_password)
            setattr(user, 'password', hashed_password)

    for key, value in updates.items():
        if value is not None:
            setattr(user, key, value)
    
    db.commit()
    db.refresh(user)
    return user

def create_project(db: Session, data: dict):
    new_project = Project(**data)
    db.add(new_project)
    db.commit()
    return new_project

def get_project_by_id(db: Session, project_id: int):
    return db.query(Project).filter(Project.id == project_id).first()

def get_all_projects(db: Session, filters: dict = None):
    query = db.query(Project)
    if filters:
        if filters.get('status'):
            query = query.filter(Project.status == filters['status'])
        if filters.get('customer'):
            query = query.filter(Project.customer.contains(filters['customer']))
        if filters.get('search'):
            query = query.filter(Project.description.contains(filters['search']) | Project.internal_number.contains(filters['search']))
        if filters.get('expert'):
            query = query.filter(Project.expert.contains(filters['expert']))
    return query.order_by(Project.created_at.desc()).all()

def update_project(db: Session, project_id: int, data: dict):
    db.query(Project).filter(Project.id == project_id).update(data)
    db.commit()

def delete_project(db: Session, project_id: int):
    project = db.query(Project).filter(Project.id == project_id).first()
    if project:
        db.delete(project)
        db.commit()

def get_task_by_id(db: Session, task_id: int):
    return db.query(Task).filter(Task.id == task_id).first()

def get_all_users(db: Session):
    return db.query(User).order_by(User.username).all()

def get_user_tasks(db: Session, user_id: int):
    return db.query(Task).filter(Task.assigned_to == user_id).order_by(Task.created_at.desc()).all()

def get_all_tasks(db: Session):
    return db.query(Task).order_by(Task.created_at.desc()).all()

def create_task(db: Session, data: dict, assigned_by: int):
    new_task = Task(
        title=data['title'],
        description=data['description'],
        task_type=data['task_type'],
        level=data['level'],
        assigned_to=data['assigned_to'],
        leader_id=data.get('leader_id'),
        start_date=data.get('start_date'),
        end_date=data.get('end_date'),
        project_id=data.get('project_id'),
        follow_up_date=data.get('follow_up_date'),
        follow_up_message=data.get('follow_up_message'),
        assigned_by=assigned_by,
        status='To Do'
    )
    db.add(new_task)
    db.commit()

def update_task_fields(db: Session, task_id: int, updates: dict):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task: return None

    if 'success_percent' in updates:
        percent = updates['success_percent']
        if percent >= 100: updates['status'] = 'Completed'
        elif percent > 0: updates['status'] = 'In Progress'
        else: updates['status'] = 'To Do'
    
    for key, value in updates.items():
        setattr(task, key, value)
    db.commit()
    db.refresh(task)
    return task

def delete_task(db: Session, task_id: int):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        db.delete(task)
        db.commit()

def create_notification(db: Session, user_id: int, task_id: int, message: str):
    exists = db.query(Notification).filter_by(user_id=user_id, task_id=task_id, is_read=0).first()
    if not exists:
        notif = Notification(user_id=user_id, task_id=task_id, message=message)
        db.add(notif)
        db.commit()

def get_unread_notifications(db: Session, user_id: int):
    return db.query(Notification).filter_by(user_id=user_id, is_read=0).order_by(Notification.created_at.desc()).all()

def mark_notification_as_read(db: Session, notification_id: int, user_id: int):
    notif = db.query(Notification).filter_by(id=notification_id, user_id=user_id).first()
    if notif:
        notif.is_read = 1
        db.commit()

def create_customer(db: Session, data: dict):
    new_customer = Customer(
        name=data['name'],
        short_name=data.get('short_name'),
        product_type=data['product_type'],
        other_product_description=data.get('other_product_description'),
        product_description=data.get('product_description'),
        website_url=data.get('website_url'),
        registration_status=data['registration_status'],
        portal_username=data.get('portal_username'),
        portal_password=data.get('portal_password'),
        last_action_description=data.get('last_action_description'),
        inquiry_portal=data.get('inquiry_portal'),
        address1=data.get('address1'),
        address2=data.get('address2')
    )
    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)
    return new_customer

def get_all_customers(db: Session, filters: dict = None):
    query = db.query(Customer)
    if filters:
        if 'search' in filters and filters['search']:
            query = query.filter(Customer.name.contains(filters['search']))
        if 'product_type' in filters and filters['product_type']:
            query = query.filter(Customer.product_type == filters['product_type'])
        if 'registration_status' in filters and filters['registration_status']:
            query = query.filter(Customer.registration_status == filters['registration_status'])
    return query.order_by(Customer.created_at.desc()).all()

def get_customer_by_id(db: Session, customer_id: int):
    return db.query(Customer).filter(Customer.id == customer_id).first()

def update_customer(db: Session, customer_id: int, data: dict):
    db.query(Customer).filter(Customer.id == customer_id).update(data)
    db.commit()

def delete_customer(db: Session, customer_id: int):
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if customer:
        db.delete(customer)
        db.commit()

# def create_customer_unit(db: Session, customer_id: int, data: dict):
#     new_unit = CustomerUnit(
#         customer_id=customer_id,
#         unit_number=data['unit_number'],
#         manager_id=data.get('manager_id'),
#         boss_id=data.get('boss_id'),
#         supervisor_id=data.get('supervisor_id')
#     )
#     db.add(new_unit)
#     db.commit()
#     db.refresh(new_unit)
#     return new_unit

# def update_customer_unit(db: Session, unit_id: int, data: dict):
#     db.query(CustomerUnit).filter(CustomerUnit.id == unit_id).update(data)
#     db.commit()

# def delete_customer_unit(db: Session, unit_id: int):
#     unit = db.query(CustomerUnit).filter(CustomerUnit.id == unit_id).first()
#     if unit:
#         db.delete(unit)
#         db.commit()

# def add_expert_to_unit(db: Session, unit_id: int, user_id: int):
#     expert = CustomerUnitExpert(unit_id=unit_id, user_id=user_id)
#     db.add(expert)
#     db.commit()
#     return expert

# def remove_expert_from_unit(db: Session, expert_id: int):
#     expert = db.query(CustomerUnitExpert).filter(CustomerUnitExpert.id == expert_id).first()
#     if expert:
#         db.delete(expert)
#         db.commit()

def create_customer_unit(db: Session, customer_id: int, unit_data: dict):
    unit = CustomerUnit(
        customer_id=customer_id,
        unit_number=unit_data["unit_number"],
        boss_name=unit_data.get("boss_name"),
        admin_name=unit_data.get("admin_name"),
        watcher_name=unit_data.get("watcher_name")
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)

    for worker_name in unit_data.get("worker_names", []):
        worker = CustomerWorker(unit_id=unit.id, name=worker_name)
        db.add(worker)
    db.commit()

def delete_all_units_for_customer(db: Session, customer_id: int):
    db.query(CustomerWorker).filter(CustomerWorker.unit_id.in_(
        db.query(CustomerUnit.id).filter(CustomerUnit.customer_id == customer_id)
    )).delete(synchronize_session=False)

    db.query(CustomerUnit).filter(CustomerUnit.customer_id == customer_id).delete(synchronize_session=False)
    db.commit()
