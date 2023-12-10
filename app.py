import datetime
from enum import Enum
import os
import random
import re
from datetime import date, datetime, timedelta

import pymongo
from bson import ObjectId
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

import db

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = APP_ROOT + "/static"

app = Flask(__name__)
app.secret_key = "poiuytrewqasdfghjkl"


# admin Views
@app.route("/admin/")
@app.route("/admin/login/", methods=["GET", "POST"])
def admin_login():
    error_msg = ""
    if request.method == "POST":
        values = {
            "username": request.form.get("username"),
            "password": request.form.get("password"),
        }

        result = db.admins.find_one(values)
        if result:
            session["logged_in"] = True
            del result["password"]
            session["fullname"] = result["fullname"]
            session["role"] = "Admin"
            return redirect(url_for("admin_home"))
        else:
            error_msg = "Invalid Login Credentials"

    admin = db.admins.find_one()
    if not admin:
        values = {"username": "admin", "password": "admin", "fullname": "Administrator"}
        db.admins.insert_one(values)

    return render_template("/login_admin.html", error_msg=error_msg)


@app.route("/admin/home/")
def admin_home():
    batches = db.batches.count_documents({})
    started_projects = db.project_Details.count_documents({})
    completed_projects = db.project_Details.count_documents(
        {"projectStatus": ProjectStatus.COMPLETED.value}
    )
    dashboard = {
        "batches": batches,
        "started_projects": started_projects,
        "completed_projects": completed_projects,
    }
    return render_template("/admin/home.html", dashboard=dashboard)


@app.route("/admin/departments", methods=["GET", "POST"])
def admin_departments():
    dept = ""
    if request.method == "POST":
        id = request.form.get("dept_id")
        name = request.form.get("name")
        if not id:
            # Add Department
            db.departments.insert_one({"name": name, "status": True})
            flash("department added successfully", "success")
            return redirect(url_for("admin_departments"))
        else:
            result = db.departments.update_one(
                {"_id": ObjectId(id)}, {"$set": {"name": name}}
            )
            if result.modified_count > 0:
                flash("department updated successfully", "success")
            else:
                flash("No changes made", "warning")

            return redirect(url_for("admin_departments"))

    if request.args.get("id"):
        dept = db.departments.find_one({"_id": ObjectId(request.args.get("id"))})

    departments = db.departments.find({"status": True}).sort("_id", -1)
    if not departments:
        return abort(404, "Departments not found")

    return render_template(
        "/admin/departments.html", departments=departments, dept=dept
    )


# delete department
@app.route("/admin/department/delete")
def admin_department_delete():
    deptId = request.args.get("id")
    dept = db.departments.find_one({"_id": ObjectId(deptId)})
    if not dept:
        return abort(404, "Departments not found")
    db.departments.update_one({"_id": ObjectId(deptId)}, {"$set": {"status": False}})
    db.departments.delete_one({"_id": ObjectId(deptId)})
    flash("department deleted successfully", "success")
    return redirect(url_for("admin_departments"))


# admin view faculties
@app.route("/admin/faculties")
def admin_faculties():
    faculties = db.faculties.aggregate(
        [
            {"$match": {"status": True}},
            {
                "$lookup": {
                    "from": db.departments.name,
                    "localField": "department_id",
                    "foreignField": "_id",
                    "as": "department",
                }
            },
            {"$unwind": "$department"},
        ]
    )
    faculties = list(faculties)
    list.reverse(faculties)
    return render_template("/admin/faculties.html", faculties=faculties)


# admin add faculty
@app.route("/admin/faculty/add", methods=["GET", "POST"])
def admin_faculty_add():
    if request.method == "POST":
        values = {
            "department_id": ObjectId(request.form.get("department_id")),
            "firstName": request.form.get("firstName"),
            "lastName": request.form.get("lastName"),
            "gender": request.form.get("gender"),
            "email": request.form.get("email"),
            "phoneNumber": request.form.get("phoneNumber"),
            "address": request.form.get("address"),
            "password": request.form.get("password"),
            "education": request.form.get("education"),
            "experience" : request.form.get("experience"),
            "status": True,
            "ispasschanged":False
        }
        db.faculties.insert_one(values)
        flash("Faculty added successfully", "success")
        return redirect(url_for("admin_faculties"))

    faculty = ""
    departments = db.departments.find({"status": True})
    genders = ["Male", "Female", "Other"]
    return render_template(
        "/admin/faculty_form.html",
        faculty=faculty,
        departments=departments,
        genders=genders,
    )


# admin faculty edit
@app.route("/admin/faculty/edit", methods=["GET", "POST"])
def admin_faculty_edit():
    if request.method == "POST":
        faculty_id = request.form.get("faculty_id")
        values = {
            "department_id": ObjectId(request.form.get("department_id")),
            "firstName": request.form.get("firstName"),
            "lastName": request.form.get("lastName"),
            "gender": request.form.get("gender"),
            "email": request.form.get("email"),
            "phoneNumber": request.form.get("phoneNumber"),
            "address": request.form.get("address"),
        }
        result = db.faculties.update_one(
            {"_id": ObjectId(faculty_id)}, {"$set": values}
        )
        if result.modified_count > 0:
            flash("Faculty updated successfully", "success")
        return redirect(url_for("admin_faculties"))

    faculty_id = request.args.get("fid")
    faculty = db.faculties.find_one({"_id": ObjectId(faculty_id)})
    if not faculty:
        return abort(404, "Faculty not found")

    departments = db.departments.find({"status": True})
    genders = ["Male", "Female", "Other"]
    return render_template(
        "/admin/faculty_form.html",
        faculty=faculty,
        departments=departments,
        genders=genders,
    )


# admin delete faculty
@app.route("/admin/faculty/delete", methods=["GET", "POST"])
def admin_faculty_delete():
    faculty_id = request.args.get("fid")
    faculty = db.faculties.find_one({"_id": ObjectId(faculty_id)})
    if not faculty:
        return abort(404, "Faculty not found")

    # Check if assigned to a project or project pending
    batches = db.batches.find({"faculty_id": ObjectId(faculty["_id"])})
    batches = list(batches)
    if not batches:
        db.faculties.update_one(
            {"_id": ObjectId(faculty_id)}, {"$set": {"status": False}}
        )
        db.faculties.delete_one( {"_id": ObjectId(faculty_id)})
        flash("Faculty deleted successfully", "success")
    else:
        flash(
            "Sorry, This faculty is assigned with a batch, remove this faculty from the batch to delete",
            "warning",
        )
    return redirect(url_for("admin_faculties"))


# admin view students
@app.route("/admin/students")
def admin_students():
    students = db.students.aggregate(
        [
            {"$match": {"status": True}},
            {
                "$lookup": {
                    "from": db.departments.name,
                    "localField": "department_id",
                    "foreignField": "_id",
                    "as": "department",
                }
            },
            {"$unwind": "$department"},
        ]
    )
    students = list(students)
    list.reverse(students)
    return render_template("/admin/students.html", students=students)


# admin add student
@app.route("/admin/student/add", methods=["GET", "POST"])
def admin_student_add():
    if request.method == "POST":
        values = {
            "department_id": ObjectId(request.form.get("department_id")),
            "regNo": int(request.form.get("regNo")),
            "firstName": request.form.get("firstName"),
            "lastName": request.form.get("lastName"),
            "gender": request.form.get("gender"),
            "email": request.form.get("email"),
            "phoneNumber": request.form.get("phoneNumber"),
            "address": request.form.get("address"),
            "password": request.form.get("password"),
            "isProjectAssigned": False,
            "isBatchAssigned": False,
            "status": True,
            "major": request.form.get("major"),
            "ispasschanged":False,

        }
        db.students.insert_one(values)
        flash("Student added successfully", "success")
        return redirect(url_for("admin_students"))

    student = ""
    reg_no = int("20231001")
    last_reg_no = db.students.find_one(
        {}, {"_id": 0, "regNo": 1}, sort=[("_id", pymongo.DESCENDING)]
    )
    print(last_reg_no)
    if last_reg_no:
        reg_no = last_reg_no["regNo"] + 1

    print(reg_no)
    departments = db.departments.find({"status": True})
    genders = ["Male", "Female", "Other"]
    student = {"regNo": reg_no}
    return render_template(
        "/admin/student_form.html",
        student=student,
        departments=departments,
        genders=genders,
    )


# admin student edit
@app.route("/admin/student/edit", methods=["GET", "POST"])
def admin_student_edit():
    if request.method == "POST":
        student_id = request.form.get("student_id")
        values = {
            "department_id": ObjectId(request.form.get("department_id")),
            "regNo": int(request.form.get("regNo")),
            "firstName": request.form.get("firstName"),
            "lastName": request.form.get("lastName"),
            "gender": request.form.get("gender"),
            "email": request.form.get("email"),
            "phoneNumber": request.form.get("phoneNumber"),
            "address": request.form.get("address"),
        }
        result = db.students.update_one({"_id": ObjectId(student_id)}, {"$set": values})
        if result.modified_count > 0:
            flash("Student updated successfully", "success")
        return redirect(url_for("admin_students"))

    student_id = request.args.get("sid")
    student = db.students.find_one({"_id": ObjectId(student_id)})
    if not student:
        return abort(404, "Student not found")

    departments = db.departments.find({"status": True})
    genders = ["Male", "Female", "Other"]
    return render_template(
        "/admin/student_form.html",
        student=student,
        departments=departments,
        genders=genders,
    )


# admin delete student
@app.route("/admin/student/delete", methods=["GET", "POST"])
def admin_student_delete():
    stud_id = request.args.get("sid")
    student = db.students.find_one({"_id": ObjectId(stud_id)})
    if not student:
        return abort(404, "Student not found")

    if not student["isBatchAssigned"]:
        db.students.update_one({"_id": ObjectId(stud_id)}, {"$set": {"status": False}})
        db.students.delete_one({"_id": ObjectId(stud_id)})
        flash("Student deleted successfully", "success")
    else:
        flash(
            "Sorry, This student is assigned with a batch, remove this student from the batch to delete",
            "warning",
        )
    return redirect(url_for("admin_students"))


# admin view batch
@app.route("/admin/batches")
def admin_batches_view():
    batches = db.batches.aggregate(
        [
            {"$match": {"status": True}},
            {
                "$lookup": {
                    "from": db.departments.name,
                    "localField": "department_id",
                    "foreignField": "_id",
                    "as": "department",
                }
            },
            {"$unwind": "$department"},
            {
                "$lookup": {
                    "from": db.faculties.name,
                    "localField": "faculty_id",
                    "foreignField": "_id",
                    "as": "faculty",
                }
            },
            {"$unwind": "$faculty"},
        ]
    )
    batches = list(batches)
    batches.reverse()
    return render_template("/admin/batches.html", batches=batches)


# admin add batch
@app.route("/admin/batch/add", methods=["GET", "POST"])
def admin_batch_add():
    if request.method == "POST":
        stud_ids = list(map(ObjectId, request.form.getlist("student_id")))
        values = {
            "batchName": request.form.get("batchName"),
            "department_id": ObjectId(request.form.get("department_id")),
            "faculty_id": ObjectId(request.form.get("faculty_id")),
            "student_ids": stud_ids,
            "isProjectTitleApproved": False,
            "isProjectCompleted": False,
            "status": True,
        }
        db.batches.insert_one(values)
        db.students.update_many(
            {"_id": {"$in": stud_ids}}, {"$set": {"isBatchAssigned": True}}
        )
        flash("Batch created successfully", "success")
        return redirect(url_for("admin_batches_view"))
    departments = db.departments.find({"status": True})
    return render_template("/admin/batch_form.html", departments=departments, batch="")


# admin edit batch
@app.route("/admin/batch/edit", methods=["GET", "POST"])
def admin_batch_edit():
    if request.method == "POST":
        batchId = request.form.get("batchId")
        # delete student ids
        db.batches.update_many(
            {"_id": ObjectId(batchId)}, {"$unset": {"student_ids": ""}}
        )

        # Update batch
        stud_ids = list(map(ObjectId, request.form.getlist("student_id")))
        values = {
            "batchName": request.form.get("batchName"),
            "department_id": ObjectId(request.form.get("department_id")),
            "faculty_id": ObjectId(request.form.get("faculty_id")),
            "student_ids": stud_ids,
        }
        result = db.batches.update_one({"_id": ObjectId(batchId)}, {"$set": values})
        if result.modified_count > 0:
            flash("Batch updated successfully", "success")
        return redirect(url_for("admin_batches_view"))

    batchId = request.args.get("bid")
    batch = db.batches.find_one({"_id": ObjectId(batchId)})

    departments = db.departments.find({"status": True})
    faculties = db.faculties.find({"status": True})
    students = db.students.find(
        {"status": True, "department_id": ObjectId(batch["department_id"])}
    )
    students = list(students)
    return render_template(
        "/admin/batch_form.html",
        departments=departments,
        faculties=faculties,
        students=students,
        batch=batch,
    )


# admin delete batch
@app.route("/admin/batch/delete", methods=["GET", "POST"])
def admin_batch_delete():
    batch_id = request.args.get("bid")
    db.batches.delete_one({"_id": ObjectId(batch_id)})
    flash("Batch Deleted Successfully", "success")
    return redirect(url_for("admin_batches_view"))


@app.route("/admin/view-batch-students")
def admin_view_batch_students():
    batchId = request.args.get("bid")
    batch = db.batches.aggregate(
        [
            {"$match": {"_id": ObjectId(batchId), "status": True}},
            {
                "$lookup": {
                    "from": db.students.name,
                    "localField": "student_ids",
                    "foreignField": "_id",
                    "as": "students",
                }
            },
        ]
    )
    batch = list(batch)

    return render_template("/admin/batch_students.html", batch=batch[0])


@app.route("/admin/delete-batch-student")
def admin_delete_batch_student():
    batchId = request.args.get("bid")
    studId = request.args.get("sid")
    result = db.batches.update_one(
        {"_id": ObjectId(batchId)},
        {"$pull": {"student_ids": ObjectId(studId)}},
    )
    if result.modified_count > 0:
        flash("Student removed from batch successfully", "success")
        db.batches.delete_one({"_id": ObjectId(batchId)})
    else:
        flash("Error removing student", "warning")
    return redirect(url_for("admin_view_batch_students", bid=batchId))


# admin view project
@app.route("/admin/view-project")
def admin_view_project():
    batchId = request.args.get("bid")
    batch = db.batches.find_one({"_id": ObjectId(batchId), "status": True})
    if not batch:
        return abort(404, "Sorry, Batch Not Found")

    project = db.project_Details.find_one({"batch_id": ObjectId(batchId)})
    project_completed_percentage = 0

    total_task_count = db.tasks.count_documents(
        {"project_id": ObjectId(project["_id"])}
    )
    completed_task_count = db.tasks.count_documents(
        {
            "project_id": ObjectId(project["_id"]),
            "taskStatus": TaskStatus.COMPLETED.value,
        }
    )
    if total_task_count > 0:
        project_completed_percentage = round(
            (completed_task_count * 100) / total_task_count
        )

    return render_template(
        "/admin/project.html",
        batch=batch,
        project=project,
        ProjectStatus=ProjectStatus,
        project_completed_percentage=project_completed_percentage,
    )


# admin view project tasks
@app.route("/admin/view-tasks")
def admin_view_tasks():
    projectId = request.args.get("pid")
    project = db.project_Details.find_one({"_id": ObjectId(projectId)})
    if not project:
        return abort(404, "Project Not Found")

    tasks = db.tasks.aggregate(
        [
            {"$match": {"project_id": ObjectId(projectId)}},
            {
                "$lookup": {
                    "from": db.batches.name,
                    "localField": "batch_id",
                    "foreignField": "_id",
                    "as": "batch",
                }
            },
            {"$unwind": "$batch"},
        ]
    )
    tasks = list(tasks)

    return render_template(
        "/admin/tasks.html",
        project=project,
        tasks=tasks,
        TaskStatus=TaskStatus,
        ProjectStatus=ProjectStatus,
    )


# admin view uploaded task reports
@app.route("/admin/view-task-reports")
def admin_view_task_reports():
    task_id = request.args.get("task_id")
    project_id = request.args.get("project_id")

    task_reports = db.task_reports.aggregate(
        [
            {"$match": {"task_id": ObjectId(task_id)}},
            {
                "$lookup": {
                    "from": db.students.name,
                    "localField": "uploadedBy",
                    "foreignField": "_id",
                    "as": "student",
                }
            },
            {"$unwind": "$student"},
        ]
    )

    task_reports = list(task_reports)
    list.reverse(task_reports)

    return render_template(
        "/admin/task_reports.html",
        task_reports=task_reports,
        task_id=task_id,
        project_id=project_id,
        TaskReportStatus=TaskReportStatus,
    )


# Faculty login
@app.route("/faculty/login", methods=["GET", "POST"])
def faculty_login():
    error_msg = ""
    if request.method == "POST":
        values = {
            "email": request.form.get("email"),
            "password": request.form.get("password"),
            "status": True,
        }

        result = db.faculties.find_one(values)
        if result:
            session["logged_in"] = True
            session["userid"] = str(result["_id"])
            del result["password"]
            session["fullname"] = result["firstName"] + " " + result["lastName"]
            session["role"] = "Faculty"
            if not result["ispasschanged"]:
                return redirect(url_for("faculty_change_password"))
            return redirect(url_for("faculty_home"))
        else:
            error_msg = "Invalid Login Credentials"

    return render_template("/login_faculty.html", error_msg=error_msg)


# faculty home
@app.route("/faculty/home")
def faculty_home():
    faculty_id = session["userid"]
    assigned_projects = db.batches.count_documents({"faculty_id": ObjectId(faculty_id)})
    completed_projects = db.batches.count_documents(
        {"faculty_id": ObjectId(faculty_id), "isProjectCompleted": True}
    )
    pending_projects = assigned_projects - completed_projects

    dashboard = {
        "assigned_projects": assigned_projects,
        "completed_projects": completed_projects,
        "pending_projects": pending_projects,
    }
    return render_template("/faculty/home.html", dashboard=dashboard)


# faculty profile
@app.route("/faculty/profile", methods=["GET", "POST"])
def faculty_profile():
    if request.method == "POST":
        faculty_id = request.form.get("faculty_id")
        values = {
            "firstName": request.form.get("firstName"),
            "lastName": request.form.get("lastName"),
            "gender": request.form.get("gender"),
            "phoneNumber": request.form.get("phoneNumber"),
            "address": request.form.get("address"),
        }
        result = db.faculties.update_one(
            {"_id": ObjectId(faculty_id)}, {"$set": values}
        )
        if result.modified_count > 0:
            flash("Profile updated successfully", "success")
        return redirect(url_for("faculty_profile"))

    faculty = db.faculties.find_one({"_id": ObjectId(session["userid"])})
    departments = db.departments.find({"status": True})
    genders = ["Male", "Female", "Other"]
    return render_template(
        "/faculty/profile.html",
        faculty=faculty,
        departments=departments,
        genders=genders,
    )


# faculty change password
@app.route("/faculty/change-password", methods=["GET", "POST"])
def faculty_change_password():
    faculty_id = session["userid"]
    if request.method == "POST":
        values = {
            "password": request.form.get("password"),
            "ispasschanged":True
        }
        db.faculties.update_one({"_id": ObjectId(faculty_id)}, {"$set": values})
        flash("Password Updated successfully", "success")
        return redirect(url_for("faculty_home"))

    return render_template("/faculty/change_password.html")


# faculty view batches
@app.route("/faculty/batches")
def faculty_view_batches():
    facultyId = session["userid"]
    batches = db.batches.aggregate(
        [
            {"$match": {"faculty_id": ObjectId(facultyId), "status": True}},
            {
                "$lookup": {
                    "from": db.departments.name,
                    "localField": "department_id",
                    "foreignField": "_id",
                    "as": "department",
                }
            },
            {"$unwind": "$department"},
            {
                "$lookup": {
                    "from": db.faculties.name,
                    "localField": "faculty_id",
                    "foreignField": "_id",
                    "as": "faculty",
                }
            },
            {"$unwind": "$faculty"},
        ]
    )
    batches = list(batches)
    batches.reverse()
    return render_template("/faculty/batches.html", batches=batches)


@app.route("/faculty/view-batch-students")
def faculty_view_batch_students():
    batchId = request.args.get("bid")
    batch = db.batches.aggregate(
        [
            {"$match": {"_id": ObjectId(batchId), "status": True}},
            {
                "$lookup": {
                    "from": db.students.name,
                    "localField": "student_ids",
                    "foreignField": "_id",
                    "as": "students",
                }
            },
        ]
    )
    batch = list(batch)

    return render_template("/faculty/batch_students.html", batch=batch[0])


# faculty view suggest project title
@app.route("/faculty/project-titles")
def faculty_view_project_title():
    batchId = request.args.get("bid")
    batch = db.batches.find_one({"_id": ObjectId(batchId)})
    if not batch:
        return abort(404, "Batch not found")

    titles = db.project_titles.find({"batchId": ObjectId(batchId)})
    titles = list(titles)
    list.reverse(titles)

    return render_template(
        "/faculty/project_titles.html",
        batch=batch,
        titles=titles,
        TitleStatus=TitleStatus,
    )


# faculty approve project title
@app.route("/faculty/title-approve")
def faculty_approve_title():
    batchId = request.args.get("bid")
    titleId = request.args.get("tid")

    title = db.project_titles.find_one({"_id": ObjectId(titleId)})
    values = {"rejectionRemarks": "", "status": TitleStatus.APPROVED.value}
    db.project_titles.update_one({"_id": ObjectId(titleId)}, {"$set": values})

    db.batches.update_one(
        {"_id": ObjectId(batchId)}, {"$set": {"isProjectTitleApproved": True}}
    )
    print(title["projectBudget"])
    proj_values = {
        "batch_id": ObjectId(batchId),
        "projectTitle": title["projectTitle"],
        "projectStatus": ProjectStatus.PENDING.value,
        "budget" : title["projectBudget"]
    }
    db.project_Details.insert_one(proj_values)

    flash("Project Title Approved Successfully", "success")
    return redirect(url_for("faculty_view_batches"))


# faculty reject project title
@app.route("/faculty/title-reject", methods=["GET", "POST"])
def faculty_reject_title():
    if request.method == "POST":
        batchId = request.form.get("batchId")
        titleId = request.form.get("titleId")
        rejectionRemarks = request.form.get("rejectionRemarks")
        db.project_titles.update_one(
            {"_id": ObjectId(titleId)},
            {
                "$set": {
                    "rejectionRemarks": rejectionRemarks,
                    "status": TitleStatus.REJECTED.value,
                }
            },
        )
        flash("Title Rejected Successfully", "success")
        return redirect(url_for("faculty_view_project_title", bid=batchId))

    batchId = request.args.get("bid")
    titleId = request.args.get("tid")

    title = db.project_titles.find_one({"_id": ObjectId(titleId)})
    return render_template("/faculty/reject_title.html", ptitle=title, batchId=batchId)


# faculty view project
@app.route("/faculty/view-project")
def faculty_view_project():
    batchId = request.args.get("bid")
    batch = db.batches.find_one({"_id": ObjectId(batchId), "status": True})
    if not batch:
        return abort(404, "Sorry, Batch Not Found")

    project = db.project_Details.find_one({"batch_id": ObjectId(batchId)})
    project_completed_percentage = 0
    total_task_count = db.tasks.count_documents(
        {"project_id": ObjectId(project["_id"])}
    )
    completed_task_count = db.tasks.count_documents(
        {
            "project_id": ObjectId(project["_id"]),
            "taskStatus": TaskStatus.COMPLETED.value,
        }
    )

    if total_task_count > 0:
        project_completed_percentage = round(
            (completed_task_count * 100) / total_task_count
        )

    return render_template(
        "/faculty/project.html",
        batch=batch,
        project=project,
        ProjectStatus=ProjectStatus,
        project_completed_percentage=project_completed_percentage,
    )


# faculty update task details
@app.route("/faculty/update-project-details", methods=["GET", "POST"])
def faculty_update_project_details():
    if request.method == "POST":
        projectId = request.form.get("projectId")
        batchId = request.form.get("batchId")
        values = {
            "startDate": request.form.get("startDate"),
            "endDate": request.form.get("endDate"),

            "remarks": request.form.get("remarks"),
            "marksObtained": float(0),
            "projectStatus": ProjectStatus.INPROGRESS.value,
        }
        db.project_Details.update_one({"_id": ObjectId(projectId)}, {"$set": values})
        flash("Project Details Updated", "success")
        return redirect(url_for("faculty_view_project", bid=batchId))

    projectId = request.args.get("pid")
    project = db.project_Details.find_one({"_id": ObjectId(projectId)})
    if not project:
        return abort(404, "Project Not Found")

    batch = db.batches.find_one({"_id": ObjectId(project["batch_id"]), "status": True})
    minDate = date.today()
    return render_template(
        "/faculty/project_form.html", batch=batch, project=project, minDate=minDate
    )


# faculty view project tasks
@app.route("/faculty/view-tasks")
def faculty_view_tasks():
    projectId = request.args.get("pid")
    project = db.project_Details.find_one({"_id": ObjectId(projectId)})
    if not project:
        return abort(404, "Project Not Found")

    tasks = db.tasks.aggregate(
        [
            {"$match": {"project_id": ObjectId(projectId)}},
            {
                "$lookup": {
                    "from": db.batches.name,
                    "localField": "batch_id",
                    "foreignField": "_id",
                    "as": "batch",
                }
            },
            {"$unwind": "$batch"},
        ]
    )
    tasks = list(tasks)

    return render_template(
        "/faculty/tasks.html",
        project=project,
        tasks=tasks,
        TaskStatus=TaskStatus,
        ProjectStatus=ProjectStatus,
    )


# faculty add task
@app.route("/faculty/task-add")
def faculty_task_add():
    projectId = request.args.get("pid")
    project = db.project_Details.find_one({"_id": ObjectId(projectId)})
    if not project:
        return abort(404, "Project Not Found")
    minDate = date.today()
    return render_template(
        "/faculty/task_form.html", project=project, task="", minDate=minDate
    )


@app.route("/faculty/task-add", methods=["POST"])
def faculty_task_add_post():
    project_id = request.form.get("project_id")
    batch_id = request.form.get("batch_id")

    sampleAttachment = ""
    file = request.files.get("sampleAttachment")
    if file.filename != "":
        sampleAttachment = file.filename

    values = {
        "project_id": ObjectId(project_id),
        "batch_id": ObjectId(batch_id),
        "taskTitle": request.form.get("taskTitle"),
        "description": request.form.get("description"),
        "deliverableContent": request.form.get("deliverableContent"),
        "startDate": request.form.get("startDate"),
        "dueDate": request.form.get("dueDate"),
        "allotedMarks": float(0),
        "obtainedMarks": float(0),
        "note": request.form.get("note"),
        "sampleAttachment": sampleAttachment,
        "isReportApproved": False,
        "taskStatus": TaskStatus.PENDING.value,
    }

    db.tasks.insert_one(values)
    if file.filename != "":
        file.save(APP_ROOT + "/images/sample/" + file.filename)

    flash("Task added successfully", "success")
    return redirect(url_for("student_view_tasks", pid=project_id))


# faculty edit task
@app.route("/faculty/task-edit")
def faculty_task_edit():
    taskId = request.args.get("tid")
    task = db.tasks.find_one({"_id": ObjectId(taskId)})
    if not task:
        return abort(404, "Task Not Found")
    project = db.project_Details.find_one({"_id": ObjectId(task["project_id"])})
    minDate = date.today()
    return render_template(
        "/faculty/task_form.html", task=task, project=project, minDate=minDate
    )


# faculty edit task post functionality
@app.route("/faculty/task-edit", methods=["POST"])
def faculty_task_edit_post():
    project_id = request.form.get("project_id")
    batch_id = request.form.get("batch_id")
    task_id = request.form.get("task_id")

    file = request.files.get("sampleAttachment")
    sampleAttachment = request.form.get("oldFile")

    if file.filename != "":
        sampleAttachment = file.filename

    values = {
        "project_id": ObjectId(project_id),
        "batch_id": ObjectId(batch_id),
        "taskTitle": request.form.get("taskTitle"),
        "description": request.form.get("description"),
        "deliverableContent": request.form.get("deliverableContent"),
        "startDate": request.form.get("startDate"),
        "dueDate": request.form.get("dueDate"),
        "allotedMarks": request.form.get("allotedMarks"),
        "obtainedMarks": float(0),
        "note": request.form.get("note"),
        "sampleAttachment": sampleAttachment,
    }

    db.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": values})
    # Save sample file if uploaded
    if file.filename != "":
        file.save(APP_ROOT + "/images/sample/" + file.filename)

    flash("Task updated successfully", "success")
    return redirect(url_for("faculty_view_tasks", pid=project_id))


# faculty view uploaded task reports
@app.route("/faculty/view-task-reports")
def faculty_view_task_reports():
    task_id = request.args.get("task_id")
    project_id = request.args.get("project_id")

    task_reports = db.task_reports.aggregate(
        [
            {"$match": {"task_id": ObjectId(task_id)}},
            {
                "$lookup": {
                    "from": db.students.name,
                    "localField": "uploadedBy",
                    "foreignField": "_id",
                    "as": "student",
                }
            },
            {"$unwind": "$student"},
        ]
    )

    task_reports = list(task_reports)
    list.reverse(task_reports)

    return render_template(
        "/faculty/task_reports.html",
        task_reports=task_reports,
        task_id=task_id,
        project_id=project_id,
        TaskReportStatus=TaskReportStatus,
    )


# Student update task report
@app.route("/faculty/correction-task-report", methods=["POST"])
def faculty_correction_task_report():
    report_id = request.form.get("report_id")
    task_id = request.form.get("task_id")
    project_id = request.form.get("project_id")
    task_marks= request.form.get("updatedMarks")
    allocat_marks=request.form.get("allocatedMarks")

    correctionFile = request.files.get("correctionFile")

    today = date.today()

    values = {
        # "correctionFile": correctionFile.filename,
        "facultyComment": request.form.get("facultyComment"),
        "taskReportStatus": TaskReportStatus.APPROVED.value, # changed the value to Approved
    }
    taskvalues={
        "obtainedMarks": task_marks,
        "allotedMarks" : allocat_marks
    }
    db.task_reports.update_one({"_id": ObjectId(report_id)}, {"$set": values})
    # db.tasks.update_one({"_id":ObjectId(project_id)})

    # db.task_reports.update_one(
    #     {"_id": ObjectId(project_id)},
    #     {"$set": {"taskReportStatus": TaskReportStatus.APPROVED.value}},
    # )
    db.tasks.update_one(
        {"_id": ObjectId(task_id)}, {"$set": {"isReportApproved": True,"obtainedMarks":task_marks,"allotedMarks" : allocat_marks,"taskStatus":2}}
    )

    # if correctionFile.filename != "":
    #     correctionFile.save(APP_ROOT + "/images/corrections/" + correctionFile.filename)
    flash("Report updated successfully", "success")
    return redirect(
        url_for("faculty_view_task_reports", task_id=task_id, project_id=project_id)
    )


# faculty approve task report and task
@app.route("/faculty/approve-task-report", methods=["GET", "POST"])
def faculty_approve_task_report():
    report_id = request.args.get("report_id")
    report = db.task_reports.find_one({"_id": ObjectId(report_id)})
    project_id = request.args.get("project_id")
    task_id = request.args.get("task_id")
    db.task_reports.update_one(
        {"_id": ObjectId(report_id)},
        {"$set": {"taskReportStatus": TaskReportStatus.APPROVED.value}},
    )
    db.tasks.update_one(
        {"_id": ObjectId(report["task_id"])}, {"$set": {"isReportApproved": True}}
    )
    flash("Task Report approved successfully", "success")
    return redirect(
        url_for("faculty_view_task_reports", project_id=project_id, task_id=task_id)
    )


# Faculty task completion
@app.route("/faculty/task-completion", methods=["POST"])
def faculty_task_completion():
    task_id = request.form.get("task_id")
    project_id = request.form.get("project_id")
    values = {
        "obtainedMarks": float(request.form.get("obtainedMarks")),
        "facultyComments": request.form.get("facultyComments"),
        "taskStatus": TaskStatus.COMPLETED.value,
    }
    db.tasks.update_one({"_id": ObjectId(task_id)}, {"$set": values})

    return redirect(url_for("faculty_view_tasks", pid=project_id))


# Faculty view sub task
@app.route("/faculty/view-sub-tasks")
def faculty_view_sub_tasks():
    project_id = request.args.get("pid")
    sub_tasks = db.sub_tasks.aggregate(
        [
            {"$match": {"project_id": ObjectId(project_id)}},
            {
                "$lookup": {
                    "from": db.students.name,
                    "localField": "student_id",
                    "foreignField": "_id",
                    "as": "student",
                }
            },
            {"$unwind": "$student"},
        ]
    )
    sub_tasks = list(sub_tasks)
    list.reverse(sub_tasks)
    return render_template(
        "/faculty/sub_tasks.html",
        project_id=project_id,
        sub_tasks=sub_tasks,
        SubTaskStatus=SubTaskStatus,
    )


# Faculty add sub task
@app.route("/faculty/add-sub-task", methods=["GET", "POST"])
def faculty_add_sub_task():
    project_id = request.args.get("pid")
    project = db.project_Details.find_one({"_id": ObjectId(project_id)})
    print(project)
    batch = db.batches.aggregate(
        [
            {"$match": {"_id": ObjectId(project["batch_id"]), "status": True}},
            {
                "$lookup": {
                    "from": db.students.name,
                    "localField": "student_ids",
                    "foreignField": "_id",
                    "as": "students",
                }
            },
        ]
    )
    batch = list(batch)
    students = batch[0]["students"]

    if request.method == "POST":
        project_id = request.form.get("project_id")
        values = {
            "project_id": ObjectId(project_id),
            "student_id": ObjectId(request.form.get("student_id")),
            "faculty_id": ObjectId(session["userid"]),
            "sub_task_title": request.form.get("sub_task_title"),
            "description": request.form.get("description"),
            "status": SubTaskStatus.PENDING.value,
        }
        db.sub_tasks.insert_one(values)
        flash("Sub task added successfully", "success")
        return redirect(url_for("student_view_sub_tasks", pid=project_id))

    return render_template(
        "/faculty/sub_task_form.html",
        project_id=project_id,
        students=students,
        stask="",
    )


# Faculty view sub tasks reports
@app.route("/faculty/view-sub-task-reports")
def faculty_view_sub_task_reports():
    sub_task_id = request.args.get("stid")
    sub_task = db.sub_tasks.find_one({"_id": ObjectId(sub_task_id)})
    sub_task_reports = db.sub_task_reports.find({"sub_task_id": ObjectId(sub_task_id)})
    sub_task_reports = list(sub_task_reports)
    list.reverse(sub_task_reports)
    return render_template(
        "/faculty/sub_task_reports.html",
        project_id=sub_task["project_id"],
        sub_task_id=sub_task_id,
        sub_task=sub_task,
        sub_task_reports=sub_task_reports,
        SubTaskReportStatus=SubTaskReportStatus,
    )


# Student add sub tasks report
@app.route("/faculty/reject-sub-task-report", methods=["GET", "POST"])
def faculty_reject_sub_task_report():
    sub_task_report_id = request.args.get("report_id")
    sub_task_id = request.args.get("sub_task_id")
    if request.method == "POST":
        sub_task_report_id = request.form.get("sub_task_report_id")


        values = {
            "facultyComment": request.form.get("facultyComment"),
            "status": SubTaskReportStatus.APPROVED.value,
        }
        sub_values={
            "allocatedMarks" : request.form.get("sub_task_allocatedMarks"),
            "updatedMarks" : request.form.get("sub_task_updatedMarks"),
            "status" : SubTaskStatus.COMPLETED.value
        }
        db.sub_tasks.update_one({
            "_id":ObjectId(sub_task_id)
        },{"$set":sub_values})

        db.sub_task_reports.update_one(
            {"_id": ObjectId(sub_task_report_id)}, {"$set": values}
        )
        flash("Marks Given successfully", "success")
        return redirect(url_for("faculty_view_sub_task_reports", stid=sub_task_id))

    return render_template(
        "/faculty/sub_task_report_correction_form.html",
        sub_task_report_id=sub_task_report_id,
        sub_task_id=sub_task_id,
    )


# faculty add sub tasks report
@app.route("/faculty/approve-sub-task-report", methods=["GET", "POST"])
def faculty_approve_sub_task_report():
    sub_task_report_id = request.args.get("report_id")
    sub_task_id = request.args.get("sub_task_id")

    db.sub_task_reports.update_one(
        {"_id": ObjectId(sub_task_report_id)},
        {"$set": {"status": SubTaskReportStatus.APPROVED.value}},
    )

    db.sub_tasks.update_one(
        {"_id": ObjectId(sub_task_id)},
        {"$set": {"status": SubTaskStatus.COMPLETED.value}},
    )

    sub_task = db.sub_tasks.find_one({"_id": ObjectId(sub_task_id)})

    flash("Sub Task approved successfully", "success")
    return redirect(url_for("faculty_view_sub_tasks", pid=sub_task["project_id"]))


# faculty update project completion
@app.route("/faculty/update-project-completion")
def faculty_update_project_completion():
    project_id = request.args.get("project_id")
    project = db.project_Details.find_one({"_id": ObjectId(project_id)})
    batch_id = request.args.get("batch_id")
    # tasks = db.tasks.aggregate(
    #     [
    #         {"$match": {"project_id": ObjectId(project_id)}},
    #         {
    #             "$group": {
    #                 "_id": "$project_id",
    #                 "totalMarks": {"$sum": "$obtainedMarks"},
    #             }
    #         },
    #     ]
    # )


    # sub_tasks = db.sub_tasks.aggregate(
    #     [
    #         {"$match": {"project_id": ObjectId(project_id)}},
    #         {
    #             "$group": {
    #                 "_id": "$project_id",
    #                 "totalMarks": {"$sum": "$updatedMarks"},
    #             }
    #         },
    #     ]
    # )

    tasks=db.tasks.find({"project_id": ObjectId(project_id)})
    tasks=list(tasks)
    tasks_total=0
    pure_task_total=0
    for i in tasks:
        try:
            tasks_total+=int(i['obtainedMarks'])
            pure_task_total+=int(i['allotedMarks'])
        except:
            pass

    sub_tasks=db.sub_tasks.find({"project_id": ObjectId(project_id)})
    sub_tasks=list(sub_tasks)
    print(sub_tasks)
    sub_tasks_total=0
    pure_sub_task_total=0
    for j in sub_tasks:
        try:
            sub_tasks_total += int(j['updatedMarks'])
            pure_sub_task_total+=int(j['allocatedMarks'])
        except:
            pass
    print(sub_tasks_total)

    total=str(int(sub_tasks_total+tasks_total))+"/"+str(int(pure_task_total+pure_sub_task_total))
    prj_values = {
        "marksObtained": str(total),
        "projectStatus": ProjectStatus.COMPLETED.value,
    }
    db.project_Details.update_one({"_id": ObjectId(project_id)}, {"$set": prj_values})
    students = db.batches.find_one(
        {"_id": ObjectId(project["batch_id"])}, {"student_ids": 1, "_id": 0}
    )
    db.students.update_many(
        {"_id": {"$in": students["student_ids"]}}, {"$set": {"isBatchAssigned": False}}
    )
    db.batches.update_one(
        {"_id": ObjectId(project["batch_id"])}, {"$set": {"isProjectCompleted": True}}
    )
    flash("Project Status Updated Successfully", "success")
    return redirect(url_for("faculty_view_project", bid=batch_id))


# Student login
@app.route("/", methods=["GET", "POST"])
@app.route("/index", methods=["GET", "POST"])
@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    error_msg = ""
    if request.method == "POST":
        values = {
            "regNo": int(request.form.get("regNo")),
            "password": request.form.get("password"),
            "status": True,
        }

        result = db.students.find_one(values)

        if result:
            session["logged_in"] = True
            session["userid"] = str(result["_id"])
            del result["password"]
            session["fullname"] = result["firstName"] + " " + result["lastName"]
            session["role"] = "Student"
            if not result["ispasschanged"]:
                return redirect(url_for("student_change_password"))
            return redirect(url_for("student_home"))
        else:
            error_msg = "Invalid Login Credentials"

    return render_template("/login_student.html", error_msg=error_msg)


# student home
@app.route("/student/home")
def student_home():
    return render_template("/student/home.html")


# student profile
@app.route("/student/profile", methods=["GET", "POST"])
def student_profile():
    if request.method == "POST":
        student_id = request.form.get("student_id")
        values = {
            "firstName": request.form.get("firstName"),
            "lastName": request.form.get("lastName"),
            "gender": request.form.get("gender"),
            "phoneNumber": request.form.get("phoneNumber"),
            "address": request.form.get("address"),
        }
        result = db.students.update_one({"_id": ObjectId(student_id)}, {"$set": values})
        if result.modified_count > 0:
            flash("Profile updated successfully", "success")
        return redirect(url_for("student_profile"))

    student = db.students.find_one({"_id": ObjectId(session["userid"])})
    departments = db.departments.find({"status": True})
    genders = ["Male", "Female", "Other"]
    return render_template(
        "/student/profile.html",
        student=student,
        departments=departments,
        genders=genders,
    )


# student change password
@app.route("/student/change-password", methods=["GET", "POST"])
def student_change_password():
    student_id = session["userid"]
    if request.method == "POST":
        values = {
            "password": request.form.get("password"),
            "ispasschanged": True
        }
        db.students.update_one({"_id": ObjectId(student_id)}, {"$set": values})
        flash("Password Updated successfully", "success")

        return redirect(url_for("student_home"))

    return render_template("/student/change_password.html")


# student view batches
@app.route("/student/batches")
def student_view_batches():
    studentId = session["userid"]
    batches = db.batches.aggregate(
        [
            {"$match": {"student_ids": {"$in": [ObjectId(studentId)]}, "status": True}},
            {
                "$lookup": {
                    "from": db.departments.name,
                    "localField": "department_id",
                    "foreignField": "_id",
                    "as": "department",
                }
            },
            {"$unwind": "$department"},
            {
                "$lookup": {
                    "from": db.faculties.name,
                    "localField": "faculty_id",
                    "foreignField": "_id",
                    "as": "faculty",
                }
            },
            {"$unwind": "$faculty"},
        ]
    )
    batches = list(batches)
    batches.reverse()
    return render_template("/student/batches.html", batches=batches)


@app.route("/student/view-batch-students")
def student_view_batch_students():
    batchId = request.args.get("bid")
    batch = db.batches.aggregate(
        [
            {"$match": {"_id": ObjectId(batchId), "status": True}},
            {
                "$lookup": {
                    "from": db.students.name,
                    "localField": "student_ids",
                    "foreignField": "_id",
                    "as": "students",
                }
            },
        ]
    )
    batch = list(batch)

    return render_template("/faculty/batch_students.html", batch=batch[0])


# student suggest project title
@app.route("/student/project-titles", methods=["GET", "POST"])
def student_suggest_project_title():
    if request.method == "POST":
        batchId = request.form.get("batchId")
        values = {
            "batchId": ObjectId(batchId),
            "projectTitle": request.form.get("projectTitle"),
            "rejectionRemarks": "",
            "status": TitleStatus.PENDING.value,
            "projectDesciption": request.form.get("projectDescription"),
            "projectBudget": request.form.get("projectBudget")
        }
        db.project_titles.insert_one(values)
        flash("Project Title suggested successfully", "success")
        return redirect(url_for("student_suggest_project_title", bid=batchId))

    batchId = request.args.get("bid")
    batch = db.batches.find_one({"_id": ObjectId(batchId)})
    if not batch:
        return abort(404, "Batch not found")

    titles = db.project_titles.find({"batchId": ObjectId(batchId)})
    titles = list(titles)
    list.reverse(titles)

    return render_template(
        "/student/project_titles.html",
        batch=batch,
        titles=titles,
        TitleStatus=TitleStatus,
    )


# student view project
@app.route("/student/view-project")
def student_view_project():
    batchId = request.args.get("bid")
    batch = db.batches.find_one({"_id": ObjectId(batchId), "status": True})
    if not batch:
        return abort(404, "Sorry, Batch Not Found")

    project = db.project_Details.find_one({"batch_id": ObjectId(batchId)})
    project_completed_percentage = 0
    total_task_count = db.tasks.count_documents(
        {"project_id": ObjectId(project["_id"])}
    )
    completed_task_count = db.tasks.count_documents(
        {
            "project_id": ObjectId(project["_id"]),
            "taskStatus": TaskStatus.COMPLETED.value,
        }
    )
    if total_task_count > 0:
        project_completed_percentage = round(
            (completed_task_count * 100) / total_task_count
        )

    return render_template(
        "/student/project.html",
        batch=batch,
        project=project,
        ProjectStatus=ProjectStatus,
        project_completed_percentage=project_completed_percentage,
    )


# student view project tasks
@app.route("/student/view-tasks")
def student_view_tasks():
    projectId = request.args.get("pid")
    project = db.project_Details.find_one({"_id": ObjectId(projectId)})
    if not project:
        return abort(404, "Project Not Found")

    tasks = db.tasks.aggregate(
        [
            {"$match": {"project_id": ObjectId(projectId)}},
            {
                "$lookup": {
                    "from": db.batches.name,
                    "localField": "batch_id",
                    "foreignField": "_id",
                    "as": "batch",
                }
            },
            {"$unwind": "$batch"},
        ]
    )
    tasks = list(tasks)
    return render_template(
        "/student/tasks.html", project=project, tasks=tasks, TaskStatus=TaskStatus
    )


# Student upload document
@app.route("/student/upload-task-report", methods=["POST"])
def student_upload_task_report():
    task_id = request.form.get("task_id")
    project_id = request.form.get("project_id")
    file = request.files.get("uploadedFile")

    today = date.today()

    values = {
        "task_id": ObjectId(task_id),
        "project_id": ObjectId(project_id),
        "uploadedFile": file.filename,
        "uploadedBy": ObjectId(session["userid"]),
        "uploadedOn": str(today),
        "studentComment": request.form.get("studentComment"),
        "facultyComment": "",
        "correctionFile": "",
        "taskReportStatus": TaskReportStatus.PENDING.value,
    }

    db.task_reports.insert_one(values)
    if file.filename != "":
        file.save(APP_ROOT + "/images/reports/" + file.filename)
    flash("Report submitted successfully", "success")
    return redirect(
        url_for(
            "student_view_task_reports",
            task_id=task_id,
            project_id=project_id,
        )
    )


# student view uploaded task reports
@app.route("/student/view-task-reports")
def student_view_task_reports():
    task_id = request.args.get("task_id")
    project_id = request.args.get("project_id")

    task_reports = db.task_reports.aggregate(
        [
            {"$match": {"task_id": ObjectId(task_id)}},
            {
                "$lookup": {
                    "from": db.students.name,
                    "localField": "uploadedBy",
                    "foreignField": "_id",
                    "as": "student",
                }
            },
            {"$unwind": "$student"},
        ]
    )

    task_reports = list(task_reports)
    list.reverse(task_reports)

    return render_template(
        "/student/task_reports.html",
        task_reports=task_reports,
        task_id=task_id,
        project_id=project_id,
        TaskReportStatus=TaskReportStatus,
    )


# Student update task report
@app.route("/student/update-task-report", methods=["POST"])
def student_update_task_report():
    report_id = request.form.get("report_id")
    task_id = request.form.get("task_id")
    project_id = request.form.get("project_id")

    file = request.files.get("uploadedFile")

    today = date.today()

    values = {
        "uploadedFile": file.filename,
        "uploadedBy": ObjectId(session["userid"]),
        "uploadedOn": str(today),
        "studentComment": request.form.get("studentComment"),
    }

    db.task_reports.update_one({"_id": ObjectId(report_id)}, {"$set": values})
    file.save(APP_ROOT + "/images/reports/" + file.filename)
    flash("Report updated successfully", "success")
    return redirect(
        url_for("student_view_task_reports", task_id=task_id, project_id=project_id)
    )


# student delete task report
@app.route("/student/delete-task-report")
def student_delete_task_report():
    report_id = request.args.get("report_id")
    task_id = request.args.get("task_id")
    project_id = request.args.get("project_id")

    db.task_reports.delete_one({"_id": ObjectId(report_id)})
    flash("Task report deleted successfully", "success")
    return redirect(
        url_for("student_view_task_reports", task_id=task_id, project_id=project_id)
    )


# Student view sub tasks
@app.route("/student/view-sub-tasks")
def student_view_sub_tasks():
    project_id = request.args.get("pid")
    project = db.project_Details.find_one({"_id": ObjectId(project_id)})
    student_id = session["userid"]
    sub_tasks = db.sub_tasks.find(
        {"project_id": ObjectId(project_id), "student_id": ObjectId(student_id)}
    )
    sub_tasks = list(sub_tasks)
    list.reverse(sub_tasks)
    return render_template(
        "/student/sub_tasks.html",
        batch_id=project["batch_id"],
        project_id=project_id,
        sub_tasks=sub_tasks,
        SubTaskStatus=SubTaskStatus,
    )


# Student view sub tasks reports
@app.route("/student/view-sub-task-reports")
def student_view_sub_task_reports():
    sub_task_id = request.args.get("stid")
    sub_task = db.sub_tasks.find_one({"_id": ObjectId(sub_task_id)})
    sub_task_reports = db.sub_task_reports.find({"sub_task_id": ObjectId(sub_task_id)})
    sub_task_reports = list(sub_task_reports)
    list.reverse(sub_task_reports)
    return render_template(
        "/student/sub_task_reports.html",
        project_id=sub_task["project_id"],
        sub_task=sub_task,
        sub_task_id=sub_task_id,
        sub_task_reports=sub_task_reports,
        SubTaskReportStatus=SubTaskReportStatus,
    )


# Student add sub tasks report
@app.route("/student/add-sub-task-report", methods=["GET", "POST"])
def student_add_sub_task_reports():
    sub_task_id = request.args.get("stid")
    if request.method == "POST":
        sub_task_id = request.form.get("sub_task_id")
        project_id = request.form.get("project_id")

        file = request.files.get("uploadedFile")
        today = date.today()

        values = {
            "sub_task_id": ObjectId(sub_task_id),
            "uploadedFile": file.filename,
            "uploadedBy": ObjectId(session["userid"]),
            "uploadedOn": str(today),
            "studentComment": request.form.get("studentComment"),
            "status": SubTaskReportStatus.PENDING.value,
        }

        db.sub_task_reports.insert_one(values)
        if file.filename != "":
            file.save(APP_ROOT + "/images/sub_reports/" + file.filename)
        flash("Report inserted successfully", "success")
        return redirect(url_for("student_view_sub_task_reports", stid=sub_task_id))

    return render_template(
        "/student/sub_task_report_form.html",
        sub_task_id=sub_task_id,
    )


# Student delete sub tasks report
@app.route("/student/delete-sub-task-report", methods=["GET", "POST"])
def student_delete_sub_task_reports():
    report_id = request.args.get("report_id")
    sub_task_id = request.args.get("sub_task_id")
    db.sub_task_reports.delete_one({"_id": ObjectId(report_id)})
    flash("Report Deleted Successfully", "success")
    return redirect(url_for("student_view_sub_task_reports", stid=sub_task_id))


# Ajax methods
@app.route("/faculty/is-email-exist")
def check_faculty_email_exist():
    email = request.args.get("email")
    faculty = db.faculties.find_one({"email": email})
    if faculty:
        return jsonify(False)
    else:
        return jsonify(True)


@app.route("/student/is-regno-exist")
def check_student_regno_exist():
    regno = request.args.get("regno")
    student = db.students.find_one({"regNo": regno})
    if student:
        return jsonify(False)
    else:
        return jsonify(True)


@app.route("/is-host-email-exist")
def check_host_email_registerd():
    email = request.args.get("email")
    host = db.hosts.find_one({"email": email})
    if host:
        return jsonify(False)
    else:
        return jsonify(True)


@app.route("/is-user-phone-exist")
def check_user_phone_registerd():
    contact_no = request.args.get("contact_no")
    user = db.users.find_one({"contact_no": contact_no})
    if user:
        return jsonify(False)
    else:
        return jsonify(True)


@app.route("/is-host-phone-exist")
def check_host_phone_registerd():
    phone = request.args.get("phone")
    host = db.hosts.find_one({"phone": phone})
    if host:
        return jsonify(False)
    else:
        return jsonify(True)


@app.route("/get-faculties-by-deptid")
def get_faculties_by_deptid():
    deptId = request.args.get("deptId")
    options = "<option value=''>-- Select --</option>"
    if deptId != "":
        faculties = db.faculties.find(
            {"status": True, "department_id": ObjectId(deptId)}
        )
        for fac in faculties:
            options += (
                "<option value="
                + str(fac["_id"])
                + ">"
                + fac["firstName"]
                + " "
                + fac["lastName"]
                + "</option>"
            )
    return options


@app.route("/get-students-by-deptid")
def get_students_by_deptid():
    deptId = request.args.get("deptId")
    checkbox = ""
    if deptId != "":
        students = db.students.find(
            {
                "status": True,
                "isBatchAssigned": False,
                "department_id": ObjectId(deptId),
            }
        )
        for i, stud in enumerate(students):
            checkbox += (
                "<div class='form-check mx-5'><input class='form-check-input' type='checkbox' name='student_id' value='"
                + str(stud["_id"])
                + "' id='"
                + str(stud["_id"])
                + "'><label class='form-check-label' for='"
                + str(stud["_id"])
                + "'>"
                + str(stud["firstName"])
                + " "
                + str(stud["lastName"])
                + " ( "
                + str(stud["regNo"])
                + " )</label></div>"
            )

    return checkbox


@app.route("/logout/")
def logout():
    session.clear()
    return redirect(url_for("student_login"))


class TitleStatus(Enum):
    PENDING = 1
    APPROVED = 2
    REJECTED = 3


class ProjectStatus(Enum):
    PENDING = 1
    INPROGRESS = 2
    COMPLETED = 3


class TaskStatus(Enum):
    PENDING = 1
    COMPLETED = 2


class SubTaskStatus(Enum):
    PENDING = 1
    COMPLETED = 2


class TaskReportStatus(Enum):
    PENDING = 1
    CORRECTION = 2
    APPROVED = 3


class SubTaskReportStatus(Enum):
    PENDING = 1
    CORRECTION = 2
    APPROVED = 3


if __name__ == "__main__":
    app.run(debug=True)
