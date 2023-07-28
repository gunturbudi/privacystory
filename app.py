import csv, os, re
from datetime import datetime
import subprocess
from sqlalchemy import func


from flask import Flask, render_template, request, jsonify, url_for, redirect, flash
from flask_bootstrap import Bootstrap
from flask_login import login_user, logout_user, login_required, current_user, LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField

from werkzeug.security import generate_password_hash, check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from flair.data import Sentence
from flair.models import SequenceTagger
model_ner = SequenceTagger.load('static/model/ner-model-roberta-aug-mr-jean-baptiste.pt')

from model import db, User, Project, Stories, StoryQuality, Entities, Dfd, Dfd_triple, Dfd_triple_group, RequirementGroup, Requirements, RequirementGroupsPatterns, RequirementsPatterns, PrivacyPattern, LogAction, PatternCategory


from feature_engineering import PrivacyPatternFeatures
pp = PrivacyPatternFeatures()
pattern_dict = pp.get_lookup_patterns()

# faster debug
# model_disclosure = TextClassifier.load('static/model/disclosure-model.pt')


# model_disclosure = None
# model_ner = None

UPLOAD_FOLDER = 'static/story_upload'

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = 'sqlite:///test.db'
app.config['SECRET_KEY'] = "sdfawfeaw2b9a5d0208a72aasdqw1231234feba25506"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['BOOTSTRAP_SERVE_LOCAL'] = True

db.init_app(app)
Bootstrap(app)

global root_dfd_folder
root_dfd_folder = "static/dfd/"

login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)


class LogFilterForm(FlaskForm):
    username = StringField('Username')
    submit = SubmitField('Get Logs')
    
def create_initial_data():
    db.create_all()
    # create initial user
    initial_user = User(username="admin", 
                        email="gunturbudi@ugm.ac.id",
                        password=generate_password_hash("InitialPassword"), # consider hashing this password for security
                        is_active=True,
                        has_consented=True)

    db.session.add(initial_user)
    db.session.commit()
    
def allowed_file(filename, allowed_extensions=['txt']):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_action(action):
    username = current_user.username
    timestamp = datetime.now()
    new_action = LogAction(username=username, action=action, timestamp=timestamp)
    db.session.add(new_action)
    db.session.commit()
    
@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User,int(user_id))
  
@app.route('/')
@login_required
def index():
    save_action("project_list")
    story_count = {}
    projects = Project.query.filter_by(user_id=current_user.id).all()
    for project in projects:
        story_count[project.id] = Stories.query.filter(Stories.project_id==project.id).count()

    return render_template('index.html', projects=projects, story_count=story_count)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            global root_dfd_folder
            root_dfd_folder = "static/dfd/" + str(current_user.id)
            save_action("login")
            flash('You have successfully logged in!')
            return redirect(url_for('index'))
        
        flash('Invalid username or password')
        
    return render_template('login.html')
  
@app.route('/logout')
@login_required
def logout():
    save_action("logout")
    logout_user()
    root_dfd_folder = "static/dfd"
    flash('You have successfully logged out!')
    return redirect(url_for('login'))

@app.route('/filter_logs', methods=['GET', 'POST'])
@login_required
def filter_logs():
    form = LogFilterForm()
    logs = None
    action_time_diff = {}
    time_differences = []

    if form.validate_on_submit():
        username = form.username.data
        logs = LogAction.query.filter_by(username=username).order_by(LogAction.timestamp.asc()).all()

        # Time difference between each subsequent action
        for i in range(1, len(logs)):
            previous_log = logs[i-1]
            current_log = logs[i]
            time_diff = (current_log.timestamp - previous_log.timestamp).total_seconds()
            current_log.time_difference = time_diff  # Store time difference in the log object
            time_differences.append({
                'time_diff': time_diff,
                'previous_action': previous_log.action,
                'current_action': current_log.action
            })

        # Time difference between learning and answer actions for each phrase number
        for log in logs:
            if 'learning phrase' in log.action:
                phrase_number = log.action.split('- ')[1].strip()
                if phrase_number not in action_time_diff:
                    action_time_diff[phrase_number] = {'learning': log.timestamp, 'answer': None, 'difference': None}
            elif 'answer phrase' in log.action:
                phrase_number = log.action.split('- ')[1].strip()
                if phrase_number in action_time_diff and action_time_diff[phrase_number]['answer'] is None:
                    action_time_diff[phrase_number]['answer'] = log.timestamp
                    action_time_diff[phrase_number]['difference'] = (action_time_diff[phrase_number]['answer'] - action_time_diff[phrase_number]['learning']).total_seconds()

    return render_template('filter_logs.html', form=form, logs=logs, action_time_diff=action_time_diff, time_differences=time_differences)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        password_confirmation = request.form['password_confirmation']
        consent = request.form.get('consent')
        if not consent:
            flash('You must agree to the informed consent form to register.')
            return redirect(url_for('register'))
        if password != password_confirmation:
            flash('Passwords do not match')
            return redirect(url_for('register'))
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('This username is already taken')
            return redirect(url_for('register'))
        
            
        user = User(username=username, email=email, password=generate_password_hash(password), is_active=True, has_consented=True)
        db.session.add(user)
        db.session.commit()
        
        flash('You have successfully registered!')
        return redirect(url_for('login'))
    
    return render_template('register.html')


@app.route('/consent')
def consent():
    return render_template('consent.html')  

@app.route('/add_project', methods=('GET', 'POST'))
@login_required
def add_project():
  if request.method == 'POST':
    save_action("add_project")
    
    name = request.form['name']

    if not name:
      flash("Name is Required")
    else:
      new_project = Project(name)

      db.session.add(new_project)
      db.session.commit()
      
      if not os.path.exists(root_dfd_folder):
        os.mkdir(root_dfd_folder)

      if not os.path.exists(root_dfd_folder + "/{}".format(name)):
        os.mkdir(root_dfd_folder + "/{}".format(name))

      flash("Project Added")

      return redirect(url_for('index'))

  return jsonify({'htmlresponse' : render_template('add_project.html')})

@app.route('/add_story', methods=('GET', 'POST'))
@login_required
def add_story():
  if request.method == 'POST':
    save_action("add_story")
    story = request.form['story']
    project_id = request.form['project_id']

    if not story:
      flash("Story is Required")
    else:
      new_story = Stories(project_id, story)

      db.session.add(new_story)
      db.session.commit()

      flash("Story Added")

      return redirect("/stories/{}".format(project_id))

  return jsonify({'htmlresponse' : render_template('add_story.html', project_id=request.args.get('project_id'))})


@app.route('/edit_story', methods=['POST'])
@login_required
def edit_story():
  if request.method == 'POST':
    save_action("edit_story")
    story_to_be_updated = Stories.query.filter_by(id=request.form['pk']).first()
    story_to_be_updated.story = request.form["value"]

    refresh_ner(request.form['pk'], request.form['value'])
    output_path = recheck_quality(story_to_be_updated.project_id)

  return jsonify({'success' : 'success'})

@app.route('/edit_backlog', methods=['POST'])
@login_required
def edit_backlog():
  if request.method == 'POST':
    save_action("edit_backlog")
    story_to_be_updated = Requirements.query.filter_by(id=request.form['pk']).first()
    story_to_be_updated.req_text = request.form["value"]
    
    db.session.commit()

  return jsonify({'success' : 'success'})

@app.route('/edit_triple', methods=['POST'])
@login_required
def edit_triple():
  if request.method == 'POST':
    save_action("edit_triple")
    triple_to_be_updated = Dfd_triple.query.filter_by(id=request.form['pk']).first()
    if request.form['name'] == 'external_entity':
      triple_to_be_updated.external_entity = request.form["value"]

    if request.form['name'] == 'process':
      triple_to_be_updated.process = request.form["value"]

    if request.form['name'] == 'data_store':
      triple_to_be_updated.data_store = request.form["value"]

    db.session.commit()

  return jsonify({'success' : 'success'})


@app.route('/regenerate_req', methods=['POST'])
@login_required
def regenerate_req():
  if request.method == 'POST':
    save_action("regenerate_req")
    story_id = request.form['story_id']
    story = Stories.query.filter_by(id=story_id).one()
    triples = Dfd_triple.query.filter(Dfd_triple.story_id==story_id).all()
    for triple in triples:
      Requirements.query.filter(Requirements.triple_id==triple.id).delete()

      privacy_requirements = generate_req(triple.external_entity, triple.process, triple.data_store, triple.external_entity)
      for req_type, req_text in privacy_requirements.items():
        new_reqs = Requirements(triple.id, req_type, req_text)
        db.session.add(new_reqs)
    
    db.session.commit()
    flash("Requirement Successfully Regenerated")

    return redirect("/stories/{}".format(story.project_id))
    

@app.route('/validate_req', methods=['POST'])
@login_required
def validate_req():
  if request.method == 'POST':
    save_action("validate_req")
    req_id = request.form['rqid']
    req = Requirements.query.filter_by(id=req_id).one()
    req.valid = request.form['rqv']

    db.session.commit()

  return jsonify({'success' : 'success'})


@app.route('/validate_req_group', methods=['POST'])
@login_required
def validate_req_group():
  if request.method == 'POST':
    save_action("validate_req_group")
    req_id = request.form['rqid']
    req = RequirementGroup.query.filter_by(id=req_id).one()
    req.valid = request.form['rqv']

    db.session.commit()

  return jsonify({'success' : 'success'})

@app.route('/unvalidate_req', methods=['POST'])
@login_required
def unvalidate_req():
  if request.method == 'POST':
    save_action("unvalidate_req")
    req_id = request.form['rqid']
    req = Requirements.query.filter_by(id=req_id).one()
    req.valid = "no"

    db.session.commit()

  return jsonify({'success' : 'success'})


@app.route('/unvalidate_req_group', methods=['POST'])
@login_required
def unvalidate_req_group():
  if request.method == 'POST':
    save_action("unvalidate_req_group")
    req_id = request.form['rqid']
    req = RequirementGroup.query.filter_by(id=req_id).one()
    req.valid = "no"

    db.session.commit()

  return jsonify({'success' : 'success'})

@app.route('/show_solution', methods=['POST'])
def show_solution():
  save_action("show_solution")
  req_id = request.form['req_id']
  project_id = request.form['prj_id']
  
  top = 5
  recommendations = []
  
  with open("LTR_resources/ltr_output_{}.txt".format(project_id), "r") as ff:
    for f in ff:
      
      if f.startswith(str(req_id)):
        top -= 1
        
        pattern_title = f.split()[2].replace("docid=","")
        recommendations.append(pattern_dict[pattern_title])
        
      if top == 0:
        break

  return jsonify({'htmlresponse' : render_template('solution.html', recommendations=recommendations)})

def refresh_ner(story_id, story):
  Entities.query.filter(Entities.story_id==story_id).delete()

  sentence = Sentence(story)

  model_ner.predict(sentence)
  
  is_disclosure = False

  for entity in sentence.get_spans('ner'):
    new_entity = Entities(story_id, entity.start_position, entity.end_position, story[entity.start_position:entity.end_position], entity.get_label("ner").value)
    if entity.get_label("ner").value == "PII" or entity.get_label("ner").value == "Processing":
      is_disclosure = True

    db.session.add(new_entity)


  story_to_be_updated = Stories.query.filter_by(id=story_id).first()

  '''
  Old Flair

  m = sentence.to_dict(tag_type='ner')

  for entity in m["entities"]:
    new_entity = Entities(story_id, entity["start_pos"], entity["end_pos"], story[entity["start_pos"]:entity["end_pos"]], entity["labels"][0].value)

    db.session.add(new_entity)

  '''



  '''
  model_disclosure.predict(sentence)
  
  story_to_be_updated.disclosure = int(sentence.labels[0].value)
  story_to_be_updated.probability_disclosure = float(sentence.labels[0].score)
  '''

  # PreDUS
  # probability = predict_disclosure(story)

  # story_to_be_updated.disclosure = 1 if probability>0.5 else 0
  # story_to_be_updated.probability_disclosure = probability
  
  # We change Predus with NER conditions. If PII or processing is present in the history, then it is likely to have disclosure
  story_to_be_updated.disclosure = is_disclosure

  db.session.commit()

@app.route('/delete_story', methods=('POST', 'DELETE'))
@login_required
def delete_story():
  if request.method == 'DELETE':
    save_action("delete_story")
    print(request.form['story_id'])
    return jsonify({'htmlresponse' : render_template('delete_story.html', story_id=request.form['story_id'])})

  elif request.method == 'POST':
    save_action("delete_story")
    
    story_id = request.form['story_id']

    story_to_be_deleted = Stories.query.filter(Stories.id==story_id).one()
    project = Project.query.filter(Project.id==story_to_be_deleted.project_id).one()

    ents_to_be_deleted = Entities.query.filter(Entities.story_id==story_id).delete(synchronize_session=False)

    dfds_to_be_deleted = Dfd_triple.query.filter(Dfd_triple.story_id==story_id).delete(synchronize_session=False)

    format_type = [".csv", ".dot", ".xml", "_dfd.png", "_robust.png", "_robust.txt"]
    for f in format_type:
      filepath = root_dfd_folder + "/{}/s_{}_{}".format(project.name, story_id, f)
      if os.path.exists(filepath):
        os.remove(filepath)

    db.session.delete(story_to_be_deleted)

    db.session.commit()

    flash("Story Deleted")

    return redirect("/stories/{}".format(story_to_be_deleted.project_id))


def import_story_from_file(project_id, story_filepath):
  with open(story_filepath, 'r') as sfs:
    for story in sfs:
      new_story = Stories(project_id, story)
      db.session.add(new_story)
      
  db.session.commit()

@app.route('/import_story', methods=('GET', 'POST'))
@login_required
def import_story():
  if request.method == 'POST':
      save_action("import_story")
    
      project_id = request.form['project_id']

      # check if the post request has the file part
      if 'file' not in request.files:
          flash('No file part')

          return redirect("/stories/{}".format(project_id))

      file = request.files['file']

      # If the user does not select a file, the browser submits an
      # empty file without a filename.
      if file.filename == '':
          flash('No selected file')
          return redirect("/stories/{}".format(project_id))

      if file and allowed_file(file.filename, ['txt']):
          filename = secure_filename(file.filename)
          file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
          import_story_from_file(project_id, os.path.join(app.config['UPLOAD_FOLDER'], filename))

      flash("Import Story Successfull")

      return redirect("/stories/{}".format(project_id))

  return jsonify({'htmlresponse' : render_template('import_story.html', project_id=request.args.get('project_id'))})

@app.route('/replace_dfd', methods=('GET', 'POST'))
@login_required
def replace_dfd():
  if request.method == 'POST':
      save_action("replace_dfd")
      
      story_id = request.form['story_id']
      story = Stories.query.filter(Stories.id==story_id).one()
      project = Project.query.filter(Project.id==story.project_id).one()

      # check if the post request has the file part
      if 'file' not in request.files:
          flash('No file part')

          return redirect("/stories/{}".format(project.id))

      file = request.files['file']

      # If the user does not select a file, the browser submits an
      # empty file without a filename.
      if file.filename == '':
          flash('No selected file')
          return redirect("/stories/{}".format(project.id))

      if file and allowed_file(file.filename, ['png']):
          # filename = secure_filename(file.filename)
          filename = root_dfd_folder + "/{}/s_{}_dfd.png".format(project.name, story_id)
          file.save(os.path.join(root_dfd_folder + "/{}".format(project.name), "s_{}_dfd.png".format(story_id)))

      flash("DFD of story \"{}\" successfully replaced".format(story.story))

      return redirect("/stories/{}".format(project.id))

  return redirect("/stories/{}".format(project.id))


@app.route('/stories/<int:project_id>')
@login_required
def stories(project_id):
  save_action("story_table")
  
  project = Project.query.filter(Project.id==project_id).one()
  stories = Stories.query.filter(Stories.project_id==project_id).all()

  # for filtering
  subject_entities = Entities.query.with_entities(Entities.label).join(Stories, Stories.id==Entities.story_id).filter(Stories.project_id==project_id, Entities.ent_type=="Data").distinct()
  processing_entities = Entities.query.with_entities(Entities.label).join(Stories, Stories.id==Entities.story_id).filter(Stories.project_id==project_id, Entities.ent_type=="Processing").distinct()
  pii_entities = Entities.query.with_entities(Entities.label).join(Stories, Stories.id==Entities.story_id).filter(Stories.project_id==project_id, Entities.ent_type=="PII").distinct()

  return render_template('stories.html', project=project, stories=stories, subject_entities=subject_entities, processing_entities=processing_entities, pii_entities=pii_entities)


@app.route('/see_group_dfd/<int:project_id>')
@login_required
def see_group_dfd(project_id):
  save_action("see_group_dfd")
  
  project = Project.query.filter(Project.id==project_id).one()
  dfds = Dfd.query.filter(project_id==project_id).all()

  return render_template('dfd.html', project=project, dfds=dfds)


@app.route('/story_table', methods=['POST'])
@login_required
def story_table():
  save_action("story_table")
  project_id = request.form['project_id']
  project = Project.query.filter(Project.id==project_id).one()

  if "entities" in request.form:
    entities = request.form['entities'].split(';')[:-1]
    stories = Stories.query.join(Entities, Stories.id==Entities.story_id).filter(Stories.project_id==project_id, Entities.label.in_(entities)).all()
  else:
    stories = Stories.query.filter(Stories.project_id==project_id).all()

  
  quality = StoryQuality.query.all()
  story_quality = {}
  for q in quality:
    story_quality[q.story_id] = q

  story_entity = {}
  story_ner = {}

  for story in stories:
    entities = Entities.query.filter(Entities.story_id==story.id).all()

    story_entity[story.id] = entities
    
    last_pos = 0
    chunks = []
    for entity in entities:
      chunks.append(story.story[last_pos:entity.start])
      ent_type = "Subject" if entity.ent_type == "Data" else entity.ent_type
      chunks.append("<mark data-entity='{}'>{}</mark>".format(ent_type, story.story[entity.start:entity.end]))
      last_pos = entity.end

    chunks.append(story.story[last_pos:])

    story_ner[story.id] = " ".join(chunks)

  return jsonify({'htmlresponse' : render_template('story_table.html', stories=stories, project=project, story_entity=story_entity, story_ner=story_ner, story_quality=story_quality)})


# reference
# https://github.com/PrettyPrinted/AJAX_Forms_jQuery_Flask/blob/master/process.py

@app.route('/aqusa', methods=['POST'])
@login_required
def aqusa():
  save_action("aqusa")
  project_id = request.form['project_id']
  project_to_be_updated = Project.query.filter_by(id=project_id).first()
  project_to_be_updated.checked_quality = 1

  db.session.commit()

  output_path = recheck_quality(project_id)

  return jsonify({'output_path' : url_for('static', filename=output_path)})

def recheck_quality(project_id):
  from aqusa.aqusainline import run_aqusa
  
  project = Project.query.filter(Project.id==project_id).one()
  stories = Stories.query.filter(Stories.project_id==project_id).all()

  output_path, defects = run_aqusa(stories, project.name)

  qualities = StoryQuality.query.join(Stories, Stories.id==StoryQuality.story_id).filter(Stories.project_id==project_id).all()
  for q in qualities:
    print("deleting old data", q.story_id)
    StoryQuality.query.filter(StoryQuality.story_id==q.story_id).delete()

  db.session.commit()

  for defect in defects:
    print("new data", defect.story_id)
    new_data = StoryQuality(defect.story_id, defect.story_title, defect.kind, defect.subkind, defect.message)
    db.session.add(new_data)

  db.session.commit()

  return output_path


@app.route('/gen_ner', methods=['POST'])
@login_required
def gen_ner():
  save_action("gen_ner")
  project_id = request.form['project_id']
  project = Project.query.filter(Project.id==project_id).one()
  stories = Stories.query.filter(Stories.project_id==project_id).all()

  project_to_be_updated = Project.query.filter_by(id=project_id).first()
  project_to_be_updated.checked_entity = 1
  project_to_be_updated.checked_disclosure = 1

  for story in stories:
    refresh_ner(story.id, story.story)

  return jsonify({'success' : 'success'})

def save_dfd_triple(csv_filename, story_id=None, dfd_id=None):
  with open(csv_filename, 'r') as csvfile:
    dfdlines = csv.reader(csvfile, delimiter=',')
    next(dfdlines)

    elements = {}
    triples = []

    for ent in dfdlines:
      if ent[-1] != "endArrow=classic":
        elements[ent[0]] = {}
        elements[ent[0]]['type'] = ent[-1]
        elements[ent[0]]['label'] = ent[1]
      else:
        if len(triples) == 0:
          triples.append([ent[3],ent[4]])
        else:
          found_pair = False
          new_triples = []
          for i, t in enumerate(triples):
            if ent[3] == t[1]:
              found_pair = True

              if len(t) == 2:
                triples[i].append(ent[4])
              else:
                new_triples.append([t[0],t[1],ent[4]])


          if not found_pair:
            triples.append([ent[3],ent[4]])

          triples.extend(new_triples)

    # remove duplicates
    # triples = list(set(map(lambda i: tuple(sorted(i)), triples)))

    for t in triples:
      if len(t) == 3:
        if elements[t[2]]['type'] != "data_base":
          continue

        if story_id:
          new_triple = Dfd_triple(story_id, elements[t[0]]['label'], elements[t[1]]['label'], elements[t[2]]['label'])
          db.session.add(new_triple)
        else:
          new_triple = Dfd_triple_group(dfd_id, elements[t[0]]['label'], elements[t[1]]['label'], elements[t[2]]['label'])
          db.session.add(new_triple)

    db.session.commit()
  

def save_dfd_triples(folder_path):
  for fl in os.listdir(folder_path):
    if not fl.endswith(".csv"):
      continue

    story_id = int(fl.split("_")[-1].replace(".csv",""))

    Dfd_triple.query.filter(Dfd_triple.story_id==story_id).delete()

    save_dfd_triple(folder_path + "/{}".format(fl), story_id=story_id)

  return True

def generate_req(role, processing, personal_data, direct_subject):
  privacy_requirements = {
    "unlinkability" : "As a {}, I want the {} data that used in {} to be protected from being linked directly or indirectly to other personal data within or outside of our system, so that an attacker cannot link it to the identity of subject in {} data".format(role, personal_data, processing, personal_data),

    "anonymity" : "As a {}, I want that the {} data to be anonymized when performing {} data, so that unwanted actors cannot directly or indirectly identify subject in {} data.".format(role, personal_data, processing, personal_data),

    "pseudonym" : "As a {}, I want that the {} data to be pseudonymized when performing {} data, so that unwanted actors cannot directly or indirectly identify subject in {} data.".format(role, personal_data, processing, personal_data),

    "undetectability" : "As a {}, I want unwanted actors to be unable to sufficiently distinguish whether or not {} data is present, so that I can safely perform {}".format(role, personal_data, processing),

    "transparency_1" : "As a {}, I want to be informed and consented that the {} data is used in {}, so that I can exercise my rights when it is used outside of this context.".format(role, personal_data, processing),

    "transparency_2" : "As a {}, I want to download a copy of {} data that used in {} at camp, so that I can check their correctness.".format(role, personal_data, processing),

    "intervenability_1" : "As a {}, I want to be able to modify the {} data that have been processed at {} without undue delay, so that I can prevent the inaccuracy of data.".format(role, personal_data, processing),

    "intervenability_2" : "As a {}, I want to be able to delete the {} data that have been processed at {} without undue delay, so that I can exercise my right.".format(role, personal_data, processing),

    "intervenability_3" : "As a {}, I want to withdraw my consent on the processing of {} on the {} data, so that I can exercise my right.".format(role, processing, personal_data),

    "confidentiality" : "As a {}, I want the {} data that processed in {} to be kept confidential, so that unwanted actors are unable to negatively influence the consistency, correctness, and availability of that data".format(role, personal_data, processing),

    "plausible_deniability" : "As a {}, I want to have the ability to deny performing {} on {} data, so that unwanted actors unable to accuse me of doing such a thing.".format(role, processing, personal_data),

    "content_awareness" : "As a {}, I want to be informed that I should not share the {} data outside of the platform, so that my privacy or data subject in {} data is not compromised.".format(role, personal_data, personal_data)

  }

  return privacy_requirements

def save_privacy_requirements(stories):
  for story in stories:

    triples = Dfd_triple.query.filter(Dfd_triple.story_id==story.id).all()
    for triple in triples:
      Requirements.query.filter(Requirements.triple_id==triple.id).delete()

      privacy_requirements = generate_req(triple.external_entity, triple.process, triple.data_store, triple.external_entity)
      for req_type, req_text in privacy_requirements.items():
        new_reqs = Requirements(triple.id, req_type, req_text)
        db.session.add(new_reqs)
  
  db.session.commit()


def save_privacy_requirement_group(dfdid):
  triples = Dfd_triple_group.query.filter(Dfd_triple_group.dfd_id==dfdid).all()
  for triple in triples:
    RequirementGroup.query.filter(RequirementGroup.triple_id==triple.id).delete()

    privacy_requirements = generate_req(triple.external_entity, triple.process, triple.data_store, triple.external_entity)
    for req_type, req_text in privacy_requirements.items():
      new_reqs = RequirementGroup(triple.id, req_type, req_text)
      db.session.add(new_reqs)
  
  db.session.commit()


@app.route('/gen_dfd', methods=['POST'])
@login_required
def gen_dfd():
  save_action("gen_dfd")
  from dfd_generation import StoryDFD

  project_id = request.form['project_id']
  project = Project.query.filter(Project.id==project_id).one()
  stories = Stories.query.filter(Stories.project_id==project_id).all()

  dd = StoryDFD(root_dfd_folder +  "/")
  dd.setStories([story.story for story in stories], [story.id for story in stories])
  dd.processDFDPerStory(project.name)

  save_dfd_triples(root_dfd_folder + "/" + project.name)
  save_privacy_requirements(stories)

  return jsonify({'success' : 'success'})

@app.route('/see_backlog/<int:project_id>')
@login_required
def see_backlog(project_id):
  save_action("see_backlog")
  requirements = Requirements.query.join(Dfd_triple, Dfd_triple.id==Requirements.triple_id).join(Stories, Stories.id==Dfd_triple.story_id).filter(Stories.project_id==project_id, Requirements.valid=="yes").all()

  requirement_group = RequirementGroup.query.join(Dfd_triple_group, Dfd_triple_group.id==RequirementGroup.triple_id).join(Dfd, Dfd.id==Dfd_triple_group.dfd_id).filter(Dfd.project_id==project_id, RequirementGroup.valid=="yes").all()

  req_ner = {}
  req_group_ner = {}
  
  for req in requirements:
      pattern = re.compile(req.dfd_triple.process, re.IGNORECASE)
      req_ner_text = pattern.sub("<mark data-entity='Processing'>{}</mark>".format(req.dfd_triple.process), req.req_text)
      
      pattern = re.compile(req.dfd_triple.data_store, re.IGNORECASE)
      req_ner_text = pattern.sub("<mark data-entity='PII'>{}</mark>".format(req.dfd_triple.data_store), req_ner_text)

      pattern = re.compile(req.dfd_triple.external_entity, re.IGNORECASE)
      req_ner_text = pattern.sub("<mark data-entity='Subject'>{}</mark>".format(req.dfd_triple.external_entity), req_ner_text)
      
      req_ner[req.id] = req_ner_text
      
  for req in requirement_group:
      pattern = re.compile(req.dfd_triple_group.process, re.IGNORECASE)
      req_ner_text = pattern.sub("<mark data-entity='Processing'>{}</mark>".format(req.dfd_triple_group.process), req.req_text)
      
      pattern = re.compile(req.dfd_triple_group.data_store, re.IGNORECASE)
      req_ner_text = pattern.sub("<mark data-entity='PII'>{}</mark>".format(req.dfd_triple_group.data_store), req_ner_text)

      pattern = re.compile(req.dfd_triple_group.external_entity, re.IGNORECASE)
      req_ner_text = pattern.sub("<mark data-entity='Subject'>{}</mark>".format(req.dfd_triple_group.external_entity), req_ner_text)
      
      req_group_ner[req.id] = req_ner_text
      
  return render_template('privacy_backlog.html', requirements=requirements, requirement_group=requirement_group, req_ner=req_ner, req_group_ner=req_group_ner, project_id=project_id)

  
def generate_features(requirements, title, group=False, req_len=0):
  lines = []
  
  for i, req in enumerate(requirements):
    print("Generating Features for Story #", req.id)
    
    story_key = i + req_len if group  else i

    features_all = pp.construct_features(req.req_text, story_key)

    for i_pattern, features in enumerate(features_all):
      line = ""
      if group:
        line += "{} qid:g{}".format(1, req.id) # 1 does not mean anything
      else:
        line += "{} qid:r{}".format(1, req.id)
        
      for i_feature, val in enumerate(features):
        line += " {}:{}".format(i_feature+1, val)

      line += " #docid={}".format(title[i_pattern].replace(" ","-"))

      lines.append(line)
      
  return lines

@app.route('/gen_pattern_recommendation', methods=['POST'])
@login_required
def gen_pattern_recommendation():
  save_action("gen_pattern_recommendation")
  project_id = request.form['project_id']
  
  requirements = Requirements.query.join(Dfd_triple, Dfd_triple.id==Requirements.triple_id).join(Stories, Stories.id==Dfd_triple.story_id).filter(Stories.project_id==project_id, Requirements.valid=="yes").all()
  requirement_group = RequirementGroup.query.join(Dfd_triple_group, Dfd_triple_group.id==RequirementGroup.triple_id).join(Dfd, Dfd.id==Dfd_triple_group.dfd_id).filter(Dfd.project_id==project_id, RequirementGroup.valid=="yes").all()

  X, title, excerpt = pp.get_corpus_pattern()

  
  all_story = [req.req_text for req in requirements]
  req_len = len(all_story)
  all_story += [req.req_text for req in requirement_group]
  
  pp.construct_story_embeddings(all_story)

  lines = generate_features(requirements, title)
  lines += generate_features(requirement_group, title, True, req_len)

  print("Done generating Features!")

  LTR_filename = "LTR_resources/ltr_{}.txt".format(project_id)
  output_LTR_filename = "LTR_resources/ltr_output_{}.txt".format(project_id)
  with open(LTR_filename, "w") as f:
    for l in lines:
        f.write(l+"\n")

  print("Ranking the Design Patterns...")

  cmd_rerank = "java -jar RankLib-2.18.jar -load LTR_resources/4_RankBoost.model -rank {} -indri {}".format(LTR_filename, output_LTR_filename)
  print(cmd_rerank)
  subprocess.run(cmd_rerank)

  top = 5
  # to do: if we want to process more than one story, we need to separate the qid.
  # the pattern already sorted in indri
  pattern_top = []
  with open(output_LTR_filename, "r") as rr:
    for r in rr:
      pattern_top.append(r.split()[2].replace("docid=",""))

  return jsonify({'success' : 'success'})

@app.route('/gen_group_dfd', methods=['POST'])
@login_required
def gen_group_dfd():
  if request.method == 'POST':
    from dfd_generation import StoryDFD
    save_action("gen_group_dfd")

    story_ids = request.form['strid'].split(";")[:-1]
    stories = []
    project_name = ""
    for story_id in story_ids:
      story = Stories.query.filter_by(id=story_id).one()
      if len(project_name) == 0:
        project = Project.query.filter(Project.id==story.project_id).one()
        project_name = project.name

      if story:
        stories.append(story.story)

    filename = 's_' + '_'.join(story_ids)

    dd = StoryDFD()
    dd.processDFDFromList(stories, project_name + "Group", filename)

    new_data = Dfd(story.project_id, '_'.join(story_ids), '###'.join(stories), filename)
    db.session.add(new_data)
    db.session.commit()

    save_dfd_triple(root_dfd_folder + "/" + project_name + "Group/" + filename + ".csv", dfd_id=new_data.id)
    save_privacy_requirement_group(new_data.id)
  
  return jsonify({'success' : 'success'})

@app.route('/see_dfd_detail', methods=['POST'])
@login_required
def see_dfd_detail():
  dfdid = request.form['dfdid']
  
  save_action("see_dfd_detail")
  
  dfd = Dfd.query.filter(Dfd.id==dfdid).one()
  project = Project.query.filter(Project.id==dfd.project_id).one()

  triples = Dfd_triple_group.query.filter(Dfd_triple_group.dfd_id==dfdid).all()

  if len(triples) == 0:
    return jsonify({'htmlresponse' : 'DFD not yet generated'})

  all_requirements = []
  for triple in triples:
    requirements = RequirementGroup.query.filter(RequirementGroup.triple_id==triple.id).all()

    for req in requirements:
      pattern = re.compile(triple.process, re.IGNORECASE)
      req.req_text = pattern.sub("<mark data-entity='Processing'>{}</mark>".format(triple.process), req.req_text)
      
      pattern = re.compile(triple.data_store, re.IGNORECASE)
      req.req_text = pattern.sub("<mark data-entity='PII'>{}</mark>".format(triple.data_store), req.req_text)

      pattern = re.compile(triple.external_entity, re.IGNORECASE)
      req.req_text = pattern.sub("<mark data-entity='Subject'>{}</mark>".format(triple.external_entity), req.req_text)


    all_requirements.append({"triples":triple,"requirements":requirements})

  url_dfd = "dfd/{}Group/{}_dfd.png".format(project.name, dfd.filename)
  url_dfd_xml = "dfd/{}Group/{}.xml".format(project.name, dfd.filename)
  url_robust = "dfd/{}Group/{}_robust.png".format(project.name, dfd.filename)

  return jsonify({'htmlresponse' : render_template('dfd_detail.html', dfd=dfd, url_dfd=url_dfd, url_robust=url_robust, url_dfd_xml=url_dfd_xml, triples=triples, all_requirements=all_requirements)})

@app.route('/delete_triple', methods=['POST'])
@login_required
def delete_triple():
  triple_id = request.form['tripleid']
  Requirements.query.filter(Requirements.triple_id==triple_id).delete()
  Dfd_triple.query.filter(Dfd_triple.id==triple_id).delete()
  save_action("delete_triple")

  db.session.commit()

  return jsonify({'htmlresponse' : 'OK'})

@app.route('/delete_triple_group', methods=['POST'])
@login_required
def delete_triple_group():
  triple_id = request.form['tripleid']
  RequirementGroup.query.filter(RequirementGroup.triple_id==triple_id).delete()
  Dfd_triple_group.query.filter(Dfd_triple_group.id==triple_id).delete()
  save_action("delete_triple_group")

  db.session.commit()

  return jsonify({'htmlresponse' : 'OK'})


@app.route('/show_dfd', methods=['POST'])
@login_required
def show_dfd():
  story_id = request.form['story_id']
  story = Stories.query.filter(Stories.id==story_id).one()
  project = Project.query.filter(Project.id==story.project_id).one()
  entities = Entities.query.filter(Entities.story_id==story_id).all()

  triples = Dfd_triple.query.filter(Dfd_triple.story_id==story_id).all()
  save_action("show_dfd")

  if len(triples) == 0:
    return jsonify({'htmlresponse' : 'DFD not yet generated'})

  all_requirements = []
  for triple in triples:
    requirements = Requirements.query.filter(Requirements.triple_id==triple.id).all()

    for req in requirements:
      pattern = re.compile(triple.process, re.IGNORECASE)
      req.req_text = pattern.sub("<mark data-entity='Processing'>{}</mark>".format(triple.process), req.req_text)
      
      pattern = re.compile(triple.data_store, re.IGNORECASE)
      req.req_text = pattern.sub("<mark data-entity='PII'>{}</mark>".format(triple.data_store), req.req_text)

      pattern = re.compile(triple.external_entity, re.IGNORECASE)
      req.req_text = pattern.sub("<mark data-entity='Subject'>{}</mark>".format(triple.external_entity), req.req_text)


    all_requirements.append({"triples":triple,"requirements":requirements})


  last_pos = 0
  chunks = []
  for entity in entities:
    chunks.append(story.story[last_pos:entity.start])
    ent_type = "Subject" if entity.ent_type == "Data" else entity.ent_type
    chunks.append("<mark data-entity='{}'>{}</mark>".format(ent_type, story.story[entity.start:entity.end]))
    last_pos = entity.end

  chunks.append(story.story[last_pos:])

  story_ner = " ".join(chunks)

    
  url_dfd = "dfd/{}/{}/s_{}_dfd.png".format(current_user.id,project.name, story_id)
  url_dfd_xml = "dfd/{}/{}/s_{}.xml".format(current_user.id,project.name, story_id)
  url_robust = "dfd/{}/{}/s_{}_robust.png".format(current_user.id,project.name, story_id)

  return jsonify({'htmlresponse' : render_template('story_dfd.html', story=story, story_ner=story_ner, url_dfd=url_dfd, url_robust=url_robust, url_dfd_xml=url_dfd_xml, all_requirements=all_requirements, triples=triples)})


@app.route('/privacy_backlog', methods=['POST'])
@login_required
def privacy_backlog():
  save_action("privacy_backlog")
  
  project_id = request.form['project_id']
  requirements = Requirements.query.join(Dfd_triple, Dfd_triple.id==Requirements.triple_id).join(Stories, Stories.id==Dfd_triple.story_id).filter(Stories.project_id==project_id, Requirements.valid=="yes").all()

  requirement_group = RequirementGroup.query.join(Dfd_triple_group, Dfd_triple_group.id==RequirementGroup.triple_id).join(Dfd, Dfd.id==Dfd_triple_group.dfd_id).filter(Dfd.project_id==project_id, RequirementGroup.valid=="yes").all()

  return jsonify({'htmlresponse' : render_template('privacy_backlog.html', requirements=requirements, requirement_group=requirement_group)})


if __name__ == "__main__":
  app.run(host='0.0.0.0', port=5000, debug=True)