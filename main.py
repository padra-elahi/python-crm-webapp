from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from auth import get_db, get_current_user, login_user, register_user
from models import (
    User, Task, Project, Notification, get_user_tasks, create_task, get_all_tasks, 
    update_task_fields, delete_task, get_task_by_id, get_all_users, update_user_profile, 
    create_project, get_all_projects, get_project_by_id, update_project, delete_project,
    create_notification, get_unread_notifications, mark_notification_as_read,Customer, CustomerUnit,
    create_customer, get_all_customers, get_customer_by_id, update_customer, delete_customer,
    create_customer_unit,delete_all_units_for_customer
)
from database import Base, engine
from datetime import datetime, date
from typing import Optional

# --- App Setup ---
app = FastAPI()
Base.metadata.create_all(bind=engine)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- Constants for Dropdowns ---
SECTIONS = ["مدیریت", "فروش", "خرید", "دفتر فنی", "دفتر طراحی", "کنترل کیفی", "کنترل پروژه", "تولید", "اداری", "مالی", "مامور خرید"]
TASK_LEVELS = ["عادی", "حائز اهمیت", "اضطراری", "فوق اضطراری"]
TASK_TYPES = ["پروژه", "مدیریتی", "گزارش", "R&D"]
PROJECT_STATUSES = ["واریز پیش پرداخت","دفتر فنی", "خرید متریال" , "تولید" , "بازرسی" , "تحویل شده", "واریز مطالبات", "عودت" , "اتمام"]

PRODUCT_TYPES = ["پیمانکار EPC", "مس", "فولاد", "نفت و گاز", "سیمان", "آلومینیوم", "سایر"]
REGISTRATION_STATUSES = ["مشتری جاری", "ثبت و تکمیل مدارک", "ثبت ناقص", "عدم اقدام", "کنسل شده"]


# --- Authentication & Profile Routes ---
@app.get("/")
def root(request: Request):
    if get_current_user(request, db=next(get_db())): return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)
    return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

@app.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "user": None, "SECTIONS": SECTIONS})

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = login_user(db, username, password)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials", "user": None, "SECTIONS": SECTIONS})
    response = RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie("user_id", str(user.id), httponly=True)
    return response

@app.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "register": True, "user": None, "SECTIONS": SECTIONS})

@app.post("/register")
def register(request: Request, username: str = Form(...), password: str = Form(...), role: str = Form(...), section: str = Form(...), db: Session = Depends(get_db)):
    if not register_user(db, username, password, role, section):
        return templates.TemplateResponse("login.html", {"request": request, "register": True, "error": "Username already exists", "user": None, "SECTIONS": SECTIONS})
    return RedirectResponse("/login", status_code=status.HTTP_302_FOUND)

@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("user_id")
    return response

@app.get("/profile")
def profile_page(request: Request, user: User = Depends(get_current_user), success: bool = False):
    if not user: return RedirectResponse("/login")
    return templates.TemplateResponse("profile.html", {"request": request, "user": user, "SECTIONS": SECTIONS, "success": success})

@app.post("/profile")
async def update_profile(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user: return RedirectResponse("/login")
    form = await request.form()
    updates = {"username": form.get("username"), "section": form.get("section"), "password": form.get("password")}
    if updates["username"] != user.username:
        if db.query(User).filter(User.username == updates["username"]).first():
            return templates.TemplateResponse("profile.html", {"request": request, "user": user, "SECTIONS": SECTIONS, "error": "This username is already taken."})
    update_user_profile(db, user.id, updates)
    return RedirectResponse("/profile?success=true", status_code=status.HTTP_302_FOUND)

# --- Notification Routes ---
@app.post("/notifications/mark-read/{notification_id}")
def mark_read(notification_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user: return RedirectResponse("/login")
    mark_notification_as_read(db, notification_id, user.id)
    return RedirectResponse(request.headers.get("referer", "/dashboard"), status_code=status.HTTP_302_FOUND)

# --- Project Routes ---
@app.get("/projects")
def projects_list(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user), status_filter: Optional[str] = Query(None), customer_filter: Optional[str] = Query(None), search_filter: Optional[str] = Query(None), expert_filter: Optional[str] = Query(None)):
    if not user: return RedirectResponse("/login")
    filters = {'status': status_filter, 'customer': customer_filter, 'search': search_filter, 'expert': expert_filter}
    projects = get_all_projects(db, filters=filters)
    customers = get_all_customers(db) 
    if projects: # Check if projects list is not empty before sorting
        projects.sort(key=lambda project: project.internal_number)
    return templates.TemplateResponse("projects.html", {"request": request, "user": user, "projects": projects, "PROJECT_STATUSES": PROJECT_STATUSES, "filters": filters, "customers":customers})

@app.get("/project/new")
def new_project_form(request: Request,db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user: return RedirectResponse("/login")
    customers = get_all_customers(db) 
    return templates.TemplateResponse("project_form.html", {"request": request, "user": user, "PROJECT_STATUSES": PROJECT_STATUSES, "project": None , "customer":customers})

@app.post("/project/new")
async def handle_create_project(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user: return RedirectResponse("/login")
    form = await request.form()
    project_data = {
        "internal_number": form.get("internal_number"), "customer": form.get("customer"), "request_number": form.get("request_number"),
        "notification_date": datetime.strptime(form.get("notification_date"), "%Y-%m-%d").date() if form.get("notification_date") else None,
        "delivery_date": datetime.strptime(form.get("delivery_date"), "%Y-%m-%d").date() if form.get("delivery_date") else None,
        "description": form.get("description"), "weight_kg": float(form.get("weight_kg")) if form.get("weight_kg") else None,
        "expert": form.get("expert"), "operator": form.get("operator"), "warranty_pp": form.get("warranty_pp"),
        "tech_office_status": form.get("tech_office_status"), "purchasing_status": form.get("purchasing_status"),
        "production_status": form.get("production_status"), "inspection_status": form.get("inspection_status"),
        "shipment_date": datetime.strptime(form.get("shipment_date"), "%Y-%m-%d").date() if form.get("shipment_date") else None,
        "invoice_date": datetime.strptime(form.get("invoice_date"), "%Y-%m-%d").date() if form.get("invoice_date") else None,
        "payment_amount": float(form.get("payment_amount")) if form.get("payment_amount") else None,
        "payment_date": datetime.strptime(form.get("payment_date"), "%Y-%m-%d").date() if form.get("payment_date") else None,
        "status": form.get("status"), "notes": form.get("notes")
    }
    create_project(db, project_data)
    return RedirectResponse("/projects", status_code=status.HTTP_302_FOUND)

@app.get("/project/{project_id}")
def project_detail(project_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user: return RedirectResponse("/login")
    project = get_project_by_id(db, project_id)
    if not project: raise HTTPException(404, "Project not found")
    customers = get_all_customers(db)
    return templates.TemplateResponse("project_detail.html", {"request": request, "user": user, "project": project, "PROJECT_STATUSES": PROJECT_STATUSES, "customer":customers})

@app.post("/project/{project_id}")
async def handle_update_project(project_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user: return RedirectResponse("/login")
    form = await request.form()
    project_data = {
        "internal_number": form.get("internal_number"), "customer": form.get("customer"), "request_number": form.get("request_number"),
        "notification_date": datetime.strptime(form.get("notification_date"), "%Y-%m-%d").date() if form.get("notification_date") else None,
        "delivery_date": datetime.strptime(form.get("delivery_date"), "%Y-%m-%d").date() if form.get("delivery_date") else None,
        "description": form.get("description"), "weight_kg": float(form.get("weight_kg")) if form.get("weight_kg") else None,
        "expert": form.get("expert"), "operator": form.get("operator"), "warranty_pp": form.get("warranty_pp"),
        "tech_office_status": form.get("tech_office_status"), "purchasing_status": form.get("purchasing_status"),
        "production_status": form.get("production_status"), "inspection_status": form.get("inspection_status"),
        "shipment_date": datetime.strptime(form.get("shipment_date"), "%Y-%m-%d").date() if form.get("shipment_date") else None,
        "invoice_date": datetime.strptime(form.get("invoice_date"), "%Y-%m-%d").date() if form.get("invoice_date") else None,
        "payment_amount": float(form.get("payment_amount")) if form.get("payment_amount") else None,
        "payment_date": datetime.strptime(form.get("payment_date"), "%Y-%m-%d").date() if form.get("payment_date") else None,
        "status": form.get("status"), "notes": form.get("notes")
    }
    update_project(db, project_id, project_data)
    return RedirectResponse(f"/project/{project_id}", status_code=status.HTTP_302_FOUND)

@app.post("/project/delete/{project_id}")
def handle_delete_project(project_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user or user.role not in ['admin', 'boss']: 
        raise HTTPException(403, "You do not have permission to delete projects.")
    delete_project(db, project_id)
    return RedirectResponse("/projects", status_code=status.HTTP_302_FOUND)

# --- API for Dynamic User Fetching ---
@app.get("/api/users-by-section")
def users_by_section(section: str, db: Session = Depends(get_db)):
    query = db.query(User)
    if section != "all":
        ##query = query.filter(or_(User.role == 'admin', User.role == 'boss', User.section == section))
        query = query.filter(or_(User.role == 'boss', User.section == section))
    users = query.order_by(User.username).all()
    return [{"id": user.id, "username": user.username} for user in users]

# --- Task Routes ---
@app.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user), search_filter: Optional[str] = Query(None), status_filter: Optional[str] = Query(None), level_filter: Optional[str] = Query(None), type_filter: Optional[str] = Query(None), section_filter: Optional[str] = Query(None), man_filter: Optional[str] = Query(None), leader_filter: Optional[str] = Query(None), project_filter: Optional[str] = Query(None)):
    if not user: return RedirectResponse("/login")
    tas = get_user_tasks(db, user.id) # You need to implement get_all_user_tasks

    total_tasks = len(tas)
    completed_tasks_count = 0
    for task in tas:
        if task.status == "Completed":
            completed_tasks_count += 1
    
    if user.role in ['admin', 'boss']:
        today = date.today()
        tasks_to_follow_up = db.query(Task).filter(Task.follow_up_date <= today, Task.status != 'Completed', Task.assigned_by == user.id).all()
        for task in tasks_to_follow_up:
            message = f"Follow up on task: '{task.title}' - {task.follow_up_message}"
            create_notification(db, user_id=user.id, task_id=task.id, message=message)
  
    notifications = get_unread_notifications(db, user.id)
    base_context = {"request": request, "user": user, "notifications": notifications, "SECTIONS": SECTIONS, "TASK_LEVELS": TASK_LEVELS, "TASK_TYPES": TASK_TYPES, "total_tasks": total_tasks, "completed_tasks_count": completed_tasks_count }
    filters = {"search": search_filter, "status": status_filter, "level": level_filter, "type": type_filter, "section": section_filter, "man":man_filter , "leader":leader_filter , "proj":project_filter}

    # --- Role-Based Logic ---
    if user.role == "boss":
        my_tasks = get_user_tasks(db, user.id)
        query = db.query(Task).options(joinedload(Task.project))
    elif user.role == "admin":
        my_tasks = get_user_tasks(db, user.id)
        query = db.query(Task).options(joinedload(Task.project)).filter(or_(Task.assigned_by == user.id, Task.leader_id == user.id))
    else: # User role
        my_tasks = get_user_tasks(db, user.id)
        query = db.query(Task).filter(Task.assigned_to == user.id).options(joinedload(Task.project))
    
    # --- Apply Filters (for roles that see more than just their own tasks) ---
    if user.role in ['admin', 'boss']:
        if search_filter: query = query.filter(Task.title.contains(search_filter))
        if status_filter:
            if status_filter == "Failed": query = query.filter(Task.end_date < date.today(), Task.status != 'Completed')
            else: query = query.filter(Task.status == status_filter)
        if level_filter: query = query.filter(Task.level == level_filter)
        if man_filter: query = query.join(User, Task.assigned_to == User.id).filter(User.username.contains(man_filter))
        if project_filter: query = query.join(Project, Task.project_id == Project.id).filter(Project.description.contains(project_filter))
        if leader_filter: query = query.join(User, Task.leader_id == User.id).filter(User.username.contains(leader_filter))
        if type_filter: query = query.filter(Task.task_type == type_filter)
        # CORRECTED SECTION FILTER LOGIC
        if section_filter:
            query = query.join(User, Task.assigned_to == User.id).filter(User.section == section_filter)
        
        all_system_tasks = query.order_by(Task.created_at.desc()).all()
        all_users = get_all_users(db)
        projects = get_all_projects(db) 
        base_context.update({"my_tasks": my_tasks, "all_system_tasks": all_system_tasks, "users": all_users, "projects": projects, "filters": filters})
        return templates.TemplateResponse("dashboard_admin.html", base_context)
    else: # User role just gets their tasks
        # Apply filters to the user's own task list
        if search_filter: query = query.filter(Task.title.contains(search_filter))
        if status_filter:
            if status_filter == "Failed": query = query.filter(Task.end_date < date.today(), Task.status != 'Completed')
            else: query = query.filter(Task.status == status_filter)
        if level_filter: query = query.filter(Task.level == level_filter)
        if type_filter: query = query.filter(Task.task_type == type_filter)

        tasks = query.order_by(Task.created_at.desc()).all()
        base_context.update({"tasks": tasks, "filters": filters})
        return templates.TemplateResponse("dashboard_user.html", base_context)


@app.get("/task/{task_id}")
def task_detail_page(task_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user: return RedirectResponse("/login")
    
    task = get_task_by_id(db, task_id)
    if not task: raise HTTPException(404, "Task not found")
    
    can_view = False
    if user.role == 'boss': can_view = True
    elif user.role == 'admin' and (task.assigned_by == user.id or task.leader_id == user.id or task.assigned_to == user.id): can_view = True
    elif user.role == 'user' and task.assigned_to == user.id: can_view = True
    if not can_view: raise HTTPException(403, "You do not have permission to view this task.")

    all_users = get_all_users(db) if user.role in ['admin', 'boss'] else None
    all_projects = get_all_projects(db) if user.role in ['admin', 'boss'] else None
    return templates.TemplateResponse("task_detail.html", {"request": request, "user": user, "task": task, "users": all_users, "projects": all_projects, "TASK_LEVELS": TASK_LEVELS, "TASK_TYPES": TASK_TYPES})

@app.post("/task/create")
async def create_new_task(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role not in ["admin", "boss"]: raise HTTPException(403, "Forbidden")
    form = await request.form()
    task_data = {
        "title": form.get("title"), "description": form.get("description"), "task_type": form.get("task_type"), "level": form.get("level"), "assigned_to": int(form.get("assigned_to")),
        "leader_id": int(form.get("leader_id")) if form.get("leader_id") and form.get('leader_id').isdigit() else None,
        "start_date": datetime.strptime(form.get("start_date"), "%Y-%m-%d").date() if form.get("start_date") else None,
        "end_date": datetime.strptime(form.get("end_date"), "%Y-%m-%d").date() if form.get("end_date") else None,
        "project_id": int(form.get("project_id")) if form.get("project_id") and form.get('project_id').isdigit() else None,
        "follow_up_date": datetime.strptime(form.get("follow_up_date"), "%Y-%m-%d").date() if form.get("follow_up_date") else None,
        "follow_up_message": form.get("follow_up_message"),
    }
    create_task(db, task_data, user.id)
    return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)

@app.post("/task/update/{task_id}")
async def update_existing_task(task_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user: return RedirectResponse("/login")
    
    form = await request.form()
    updates = {}
    
    if 'success_percent' in form: updates["success_percent"] = float(form['success_percent'])
    if 'user_comment' in form: updates["user_comment"] = form['user_comment']
        
    if user.role in ['admin', 'boss']:
        updates.update({
            "level": form.get('level'), 
            "task_type": form.get('task_type'), 
            "admin_comment": form.get('admin_comment'),
        })
        if form.get('assigned_to'): updates["assigned_to"] = int(form.get('assigned_to'))
        if form.get('leader_id'): updates["leader_id"] = int(form.get('leader_id')) if form.get('leader_id').isdigit() else None
        if form.get("project_id"): updates["project_id"] = int(form.get("project_id")) if form.get('project_id').isdigit() else None
        if form.get("start_date"): updates["start_date"] = datetime.strptime(form.get("start_date"), "%Y-%m-%d").date()
        if form.get("end_date"): updates["end_date"] = datetime.strptime(form.get("end_date"), "%Y-%m-%d").date()
        if form.get("follow_up_date"): updates["follow_up_date"] = datetime.strptime(form.get("follow_up_date"), "%Y-%m-%d").date()
        if form.get("follow_up_message"): updates["follow_up_message"] = form.get("follow_up_message")

    update_task_fields(db, task_id, updates)
    return RedirectResponse(f"/task/{task_id}", status_code=status.HTTP_302_FOUND)

@app.post("/task/delete/{task_id}")
def remove_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role not in ["admin", "boss"]: raise HTTPException(403, "Forbidden")
    delete_task(db, task_id)
    return RedirectResponse("/dashboard", status_code=status.HTTP_302_FOUND)

# # --- Customer List with Filters ---
# @app.get("/customers")
# def customers_list(
#     request: Request,
#     db: Session = Depends(get_db),
#     user: User = Depends(get_current_user),
#     search: str = Query(None),
#     product_type: str = Query(None),
#     registration_status: str = Query(None)
# ):
#     if not user or user.role != "boss":
#         return RedirectResponse("/login")
    
#     filters = {
#         "search": search,
#         "product_type": product_type,
#         "registration_status": registration_status
#     }
#     customers = get_all_customers(db, filters)
    
#     # Show limited info in the list: name, short_name, product_type, registration_status
#     return templates.TemplateResponse("customers_list.html", {
#         "request": request,
#         "user": user,
#         "customers": customers,
#         "filters": filters,
#         "PRODUCT_TYPES": PRODUCT_TYPES,
#         "REGISTRATION_STATUSES": REGISTRATION_STATUSES
#     })

# # --- New Customer Form ---
# @app.get("/customers/new")
# def new_customer_form(request: Request, user: User = Depends(get_current_user)):
#     if not user or user.role != "boss":
#         return RedirectResponse("/login")
#     return templates.TemplateResponse("customer_form.html", {
#         "request": request,
#         "user": user,
#         "customer": None,
#         "PRODUCT_TYPES": PRODUCT_TYPES,
#         "REGISTRATION_STATUSES": REGISTRATION_STATUSES
#     })

# # --- Create Customer POST Handler ---
# @app.post("/customers/new")
# async def create_new_customer(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
#     if not user or user.role != "boss":
#         return RedirectResponse("/login")
#     form = await request.form()
#     data = {
#         "name": form.get("name"),
#         "short_name": form.get("short_name"),
#         "product_type": form.get("product_type"),
#         "other_product_description": form.get("other_product_description") if form.get("product_type") == "سایر" else None,
#         "product_description": form.get("product_description"),
#         "website_url": form.get("website_url"),
#         "registration_status": form.get("registration_status"),
#         "tracking_system_user": form.get("tracking_system_user"),
#         "tracking_system_password": form.get("tracking_system_password"),
#         "last_action_description": form.get("last_action_description"),
#         "inquiry_portal": form.get("inquiry_portal"),
#         "address1": form.get("address1"),
#         "address2": form.get("address2"),
#     }
#     create_customer(db, data)
#     return RedirectResponse("/customers", status_code=status.HTTP_302_FOUND)

# # --- Customer Detail & Edit Form ---
# @app.get("/customer/{customer_id}")
# def customer_detail(customer_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
#     if not user or user.role != "boss":
#         return RedirectResponse("/login")
#     customer = get_customer_by_id(db, customer_id)
#     if not customer:
#         raise HTTPException(404, "Customer not found")

#     # Load all users for dropdowns in units
#     all_users = get_all_users(db)
    
#     return templates.TemplateResponse("customer_detail.html", {
#         "request": request,
#         "user": user,
#         "customer": customer,
#         "all_users": all_users,
#         "PRODUCT_TYPES": PRODUCT_TYPES,
#         "REGISTRATION_STATUSES": REGISTRATION_STATUSES
#     })

# # --- Update Customer POST ---
# @app.post("/customer/{customer_id}")
# async def update_existing_customer(customer_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
#     if not user or user.role != "boss":
#         return RedirectResponse("/login")
#     form = await request.form()
#     data = {
#         "name": form.get("name"),
#         "short_name": form.get("short_name"),
#         "product_type": form.get("product_type"),
#         "other_product_description": form.get("other_product_description") if form.get("product_type") == "سایر" else None,
#         "product_description": form.get("product_description"),
#         "website_url": form.get("website_url"),
#         "registration_status": form.get("registration_status"),
#         "tracking_system_user": form.get("tracking_system_user"),
#         "tracking_system_password": form.get("tracking_system_password"),
#         "last_action_description": form.get("last_action_description"),
#         "inquiry_portal": form.get("inquiry_portal"),
#         "address1": form.get("address1"),
#         "address2": form.get("address2"),
#     }
#     update_customer(db, customer_id, data)
#     return RedirectResponse(f"/customer/{customer_id}", status_code=status.HTTP_302_FOUND)

# # --- Delete Customer ---
# @app.post("/customer/delete/{customer_id}")
# def delete_existing_customer(customer_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
#     if not user or user.role != "boss":
#         raise HTTPException(403, "Forbidden")
#     delete_customer(db, customer_id)
#     return RedirectResponse("/customers", status_code=status.HTTP_302_FOUND)

# # --- Customer Units Handling ---

# # Add new unit for customer
# @app.post("/customer/{customer_id}/unit/new")
# async def create_new_customer_unit(customer_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
#     if not user or user.role != "boss":
#         return RedirectResponse("/login")
#     form = await request.form()
#     data = {
#         "unit_number": int(form.get("unit_number")),
#         "manager_id": int(form.get("manager_id")) if form.get("manager_id") else None,
#         "boss_id": int(form.get("boss_id")) if form.get("boss_id") else None,
#         "supervisor_id": int(form.get("supervisor_id")) if form.get("supervisor_id") else None
#     }
#     create_customer_unit(db, customer_id, data) 
#     return RedirectResponse(f"/customer/{customer_id}", status_code=status.HTTP_302_FOUND)

# # Update existing unit
# @app.post("/customer/unit/{unit_id}/update")
# async def update_customer_unit_route(unit_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
#     if not user or user.role != "boss":
#         return RedirectResponse("/login")
#     form = await request.form()
#     data = {
#         "unit_number": int(form.get("unit_number")),
#         "manager_id": int(form.get("manager_id")) if form.get("manager_id") else None,
#         "boss_id": int(form.get("boss_id")) if form.get("boss_id") else None,
#         "supervisor_id": int(form.get("supervisor_id")) if form.get("supervisor_id") else None
#     }
#     update_customer_unit(db, unit_id, data)
#     # Redirect to the parent customer's detail page
#     # For that, fetch unit to get customer_id
#     unit = db.query(CustomerUnit).filter(CustomerUnit.id == unit_id).first()
#     if not unit:
#         raise HTTPException(404, "Unit not found")
#     return RedirectResponse(f"/customer/{unit.customer_id}", status_code=status.HTTP_302_FOUND)

# # Delete unit
# @app.post("/customer/unit/{unit_id}/delete")
# def delete_customer_unit_route(unit_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
#     if not user or user.role != "boss":
#         raise HTTPException(403, "Forbidden")
#     unit = db.query(CustomerUnit).filter(CustomerUnit.id == unit_id).first()
#     if not unit:
#         raise HTTPException(404, "Unit not found")
#     customer_id = unit.customer_id
#     delete_customer_unit(db, unit_id)
#     return RedirectResponse(f"/customer/{customer_id}", status_code=status.HTTP_302_FOUND)

# # Add expert to unit
# @app.post("/customer/unit/{unit_id}/expert/add")
# async def add_expert(unit_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
#     if not user or user.role != "boss":
#         raise HTTPException(403, "Forbidden")
#     form = await request.form()
#     user_id = int(form.get("user_id"))
#     add_expert_to_unit(db, unit_id, user_id)
#     # Redirect back to customer detail page
#     unit = db.query(CustomerUnit).filter(CustomerUnit.id == unit_id).first()
#     if not unit:
#         raise HTTPException(404, "Unit not found")
#     return RedirectResponse(f"/customer/{unit.customer_id}", status_code=status.HTTP_302_FOUND)

# # Remove expert from unit
# @app.post("/customer/unit/expert/{expert_id}/remove")
# def remove_expert_route(expert_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
#     if not user or user.role != "boss":
#         raise HTTPException(403, "Forbidden")
#     expert = db.query(CustomerUnitExpert).filter(CustomerUnitExpert.id == expert_id).first()
#     if not expert:
#         raise HTTPException(404, "Expert not found")
#     customer_id = expert.unit.customer_id if expert.unit else None
#     remove_expert_from_unit(db, expert_id)
#     if customer_id:
#         return RedirectResponse(f"/customer/{customer_id}", status_code=status.HTTP_302_FOUND)
#     return RedirectResponse("/customers", status_code=status.HTTP_302_FOUND)

# # --- Customer Org Chart Route (placeholder) ---
# @app.get("/customer/{customer_id}/org-chart")
# def customer_org_chart(customer_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
#     if not user or user.role != "boss":
#         return RedirectResponse("/login")
#     customer = get_customer_by_id(db, customer_id)
#     if not customer:
#         raise HTTPException(404, "Customer not found")
    
#     # Prepare data for chart rendering (you can enhance this in your frontend)
#     units = customer.units
#     return templates.TemplateResponse("customer_org_chart.html", {
#         "request": request,
#         "user": user,
#         "customer": customer,
#         "units": units,
#     })

# @app.get("/customer/{customer_id}/edit")
# async def edit_customer_form(customer_id: int, request: Request, db: Session = Depends(get_db)):
#     customer = db.query(Customer).filter(Customer.id == customer_id).first()
#     if not customer:
#         return templates.TemplateResponse("404.html", {"request": request})
#     return templates.TemplateResponse("customer_edit.html", {
#         "request": request,
#         "customer": customer,
#         "PRODUCT_TYPES": PRODUCT_TYPES,
#         "REGISTRATION_STATUSES": REGISTRATION_STATUSES,
#     })

# @app.post("/customer/{customer_id}/edit")
# async def update_customer(customer_id: int, request: Request, db: Session = Depends(get_db)):
#     form = await request.form()
#     form = dict(form)

#     customer = db.query(Customer).filter(Customer.id == customer_id).first()
#     if not customer:
#         return templates.TemplateResponse("404.html", {"request": request})

#     # به‌روزرسانی فیلدهای مشتری
#     customer.name = form.get("name")
#     customer.short_name = form.get("short_name")
#     customer.product_type = form.get("product_type")
#     customer.other_product_description = form.get("product_type_description") or None
#     customer.product_description = form.get("product_description")
#     customer.website_url = form.get("website_link")
#     customer.registration_status = form.get("registration_status")
#     customer.portal_username = form.get("portal_username")
#     customer.portal_password = form.get("portal_password")
#     customer.last_action_description = form.get("latest_notes")
#     customer.inquiry_portal = form.get("portal_url")
#     customer.address1 = form.get("address1")
#     customer.address2 = form.get("address2")

#     db.flush()

#     # پردازش واحدهای مشتری
#     unit_indexes = [key.split("_")[-1] for key in form if key.startswith("unit_number_")]
#     seen_unit_ids = set()

#     for idx in unit_indexes:
#         unit_id = form.get(f"unit_id_{idx}")
#         unit_number = form.get(f"unit_number_{idx}")
#         manager = form.get(f"manager_{idx}")
#         boss = form.get(f"boss_{idx}")
#         supervisor = form.get(f"supervisor_{idx}")

#         if unit_id:
#             unit = db.query(CustomerUnit).filter(CustomerUnit.id == int(unit_id)).first()
#             if not unit:
#                 continue
#             seen_unit_ids.add(unit.id)
#         else:
#             unit = CustomerUnit(customer_id=customer.id)
#             db.add(unit)
#             db.flush()

#         unit.unit_number = int(unit_number or 0)
#         unit.manager = manager
#         unit.boss = boss
#         unit.supervisor = supervisor
#         db.flush()

#         # حذف کارشناسان قبلی
#         db.query(CustomerUnitExpert).filter(CustomerUnitExpert.unit_id == unit.id).delete()
#         db.flush()

#         # اضافه کردن کارشناسان جدید
#         for key in form:
#             if key.startswith(f"expert_{idx}_"):
#                 expert_name = form.get(key)
#                 if expert_name:
#                     expert = CustomerUnitExpert(unit_id=unit.id, name=expert_name)
#                     db.add(expert)

#     # حذف واحدهای حذف شده
#     existing_units = db.query(CustomerUnit).filter(CustomerUnit.customer_id == customer.id).all()
#     for unit in existing_units:
#         if unit.id not in seen_unit_ids:
#             db.query(CustomerUnitExpert).filter(CustomerUnitExpert.unit_id == unit.id).delete()
#             db.delete(unit)

#     db.commit()

#     return RedirectResponse(url=f"/customer/{customer_id}", status_code=303)

# --- Customers Routes ---
@app.get("/customers")
def Customers_list(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user), search: str = Query(None), product_type: str = Query(None),registration_status: str = Query(None)):
    if not user: return RedirectResponse("/login")
    if user.role not in ['boss'] :
        raise HTTPException(403, "You do not have permission.")
    filters = {"search": search,"product_type": product_type,"registration_status": registration_status}
    customers = get_all_customers(db, filters=filters)
    return templates.TemplateResponse("customer_list.html", {"request": request,"user": user,"customers": customers,"filters": filters,"PRODUCT_TYPES": PRODUCT_TYPES,"REGISTRATION_STATUSES": REGISTRATION_STATUSES})

@app.get("/customer/new")
def new_customer_form(request: Request, user: User = Depends(get_current_user)):
    if not user: return RedirectResponse("/login")
    if user.role not in ['boss'] :
        raise HTTPException(403, "You do not have permission.")
    return templates.TemplateResponse("customer_form.html", {"request": request,"customer": None,"PRODUCT_TYPES": PRODUCT_TYPES,"REGISTRATION_STATUSES": REGISTRATION_STATUSES})

@app.post("/customer/new")
async def create_new_customer(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user: return RedirectResponse("/login")
    form = await request.form()
    if user.role not in ['boss'] :
        raise HTTPException(403, "You do not have permission.")
    data = {
        "name": form.get("name"),
        "short_name": form.get("short_name"),
        "product_type": form.get("product_type"),
        "other_product_description": form.get("other_product_description") if form.get("product_type") == "سایر" else None,
        "product_description": form.get("product_description"),
        "website_url": form.get("website_url"),
        "registration_status": form.get("registration_status"),
        "portal_username": form.get("portal_username"),
        "portal_password": form.get("portal_password"),
        "last_action_description": form.get("last_action_description"),
        "inquiry_portal": form.get("inquiry_portal"),
        "address1": form.get("address1"),
        "address2": form.get("address2")
    }
    units_data = []
    unit_numbers = form.getlist("unit_number[]")
    boss_names = form.getlist("boss_name[]")
    admin_names = form.getlist("admin_name[]")
    watcher_names = form.getlist("watcher_name[]")
    worker_names_list = form.getlist("worker_names[]")  # comma-separated

    for i in range(len(unit_numbers)):
        units_data.append({
            "unit_number": unit_numbers[i],
            "boss_name": boss_names[i],
            "admin_name": admin_names[i],
            "watcher_name": watcher_names[i],
            "worker_names": [name.strip() for name in worker_names_list[i].split(",") if name.strip()]
        })
    new_customer = create_customer(db, data)  # اینجا باید نتیجه را بگیرید چون نیاز دارید آیدی آن را
    for unit_data in units_data:
        create_customer_unit(db, new_customer.id, unit_data)  # از آیدی مشتری تازه ایجاد شده استفاده کنید
    return RedirectResponse("/customers", status_code=status.HTTP_302_FOUND)

@app.get("/customer/{customer_id}")
def customer_detail(customer_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user: return RedirectResponse("/login")
    if user.role not in ['boss'] :
        raise HTTPException(403, "You do not have permission.")
    customer = get_customer_by_id(db, customer_id)
    all_users = get_all_users(db)
    if not customer: raise HTTPException(404, "customer not found")
    return templates.TemplateResponse("customer_detail.html", {"request": request,"user": user,"customer": customer,"all_users": all_users,"PRODUCT_TYPES": PRODUCT_TYPES,"REGISTRATION_STATUSES": REGISTRATION_STATUSES})

@app.post("/customer/{customer_id}")
async def update_existing_customer(customer_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user: return RedirectResponse("/login")
    if user.role not in ['boss'] :
        raise HTTPException(403, "You do not have permission.")
    form = await request.form()
    data = {
        "name": form.get("name"),
        "short_name": form.get("short_name"),
        "product_type": form.get("product_type"),
        "other_product_description": form.get("other_product_description") if form.get("product_type") == "سایر" else None,
        "product_description": form.get("product_description"),
        "website_url": form.get("website_url"),
        "registration_status": form.get("registration_status"),
        "portal_username": form.get("portal_username"),
        "portal_password": form.get("portal_password"),
        "last_action_description": form.get("last_action_description"),
        "inquiry_portal": form.get("inquiry_portal"),
        "address1": form.get("address1"),
        "address2": form.get("address2")
    }
    units_data = []
    unit_numbers = form.getlist("unit_number[]")
    boss_names = form.getlist("boss_name[]")
    admin_names = form.getlist("admin_name[]")
    watcher_names = form.getlist("watcher_name[]")
    worker_names_list = form.getlist("worker_names[]")  # comma-separated

    for i in range(len(unit_numbers)):
        units_data.append({
            "unit_number": unit_numbers[i],
            "boss_name": boss_names[i],
            "admin_name": admin_names[i],
            "watcher_name": watcher_names[i],
            "worker_names": [name.strip() for name in worker_names_list[i].split(",") if name.strip()]
        })

    update_customer(db, customer_id, data)
    delete_all_units_for_customer(db, customer_id)
    for unit_data in units_data:
        create_customer_unit(db, customer_id, unit_data)

    return RedirectResponse(f"/customer/{customer_id}", status_code=status.HTTP_302_FOUND)

@app.post("/customer/{customer_id}/delete")
async def delete_customer_route(customer_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        return RedirectResponse("/login")
    if user.role not in ["boss"]:
        raise HTTPException(status_code=403, detail="You do not have permission.")
    delete_customer(db, customer_id)
    return RedirectResponse("/customers", status_code=status.HTTP_302_FOUND)


@app.get("/customer/{customer_id}/edit")
def edit_customer_form(customer_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    if user.role not in ['boss']:
        raise HTTPException(403, "You do not have permission.")
    
    customer = get_customer_by_id(db, customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")
    
    # Send customer and other necessary data to template
    return templates.TemplateResponse(
        "customer_form.html",
        {
            "request": request,
            "customer": customer,
            "form_action": f"/customer/{customer_id}",
            "form_title": "ویرایش مشتری",
            "PRODUCT_TYPES": PRODUCT_TYPES,
            "REGISTRATION_STATUSES": REGISTRATION_STATUSES
        }
    )

@app.post("/customer/{customer_id}")
async def update_existing_customer(customer_id: int, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user:
        return RedirectResponse("/login")
    if user.role not in ['boss']:
        raise HTTPException(403, "You do not have permission.")

    form = await request.form()

    data = {
        "name": form.get("name"),
        "short_name": form.get("short_name"),
        "product_type": form.get("product_type"),
        "other_product_description": form.get("other_product_description") if form.get("product_type") == "سایر" else None,
        "product_description": form.get("product_description"),
        "website_url": form.get("website_url"),
        "registration_status": form.get("registration_status"),
        "portal_username": form.get("portal_username"),
        "portal_password": form.get("portal_password"),
        "last_action_description": form.get("last_action_description"),
        "inquiry_portal": form.get("inquiry_portal"),
        "address1": form.get("address1"),
        "address2": form.get("address2")
    }

    # Collect units data
    units_data = []
    unit_numbers = form.getlist("unit_number[]")
    boss_names = form.getlist("boss_name[]")
    admin_names = form.getlist("admin_name[]")
    watcher_names = form.getlist("watcher_name[]")
    worker_names_list = form.getlist("worker_names[]")

    for i in range(len(unit_numbers)):
        units_data.append({
            "unit_number": unit_numbers[i],
            "boss_name": boss_names[i],
            "admin_name": admin_names[i],
            "watcher_name": watcher_names[i],
            "worker_names": [name.strip() for name in worker_names_list[i].split(",") if name.strip()]
        })

    update_customer(db, customer_id, data)

    # Delete all previous units and add new ones
    delete_all_units_for_customer(db, customer_id)
    for unit_data in units_data:
        create_customer_unit(db, customer_id, unit_data)

    return RedirectResponse(f"/customer/{customer_id}", status_code=status.HTTP_302_FOUND)
