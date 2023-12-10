from bson import ObjectId
import pymongo

dbClient = pymongo.MongoClient("mongodb://localhost:27017/")
db = dbClient["rse_db"]

admins = db["Admins"]
departments = db["Departments"]
faculties = db["Faculties"]
students = db["Students"]
batches = db["Batches"]
project_titles = db["Project_Titles"]
project_Details = db["Project_Details"]
tasks = db["Tasks"]
task_reports = db["TaskReports"]
sub_tasks = db["Sub_Tasks"]
sub_task_reports = db["Sub_TaskReports"]
