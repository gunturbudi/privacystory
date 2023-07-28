from flask_sqlalchemy import SQLAlchemy
from rdflib import Graph, Namespace, Literal, URIRef, BNode, RDFS
from rdflib.namespace import RDF, RDFS, OWL, FOAF
from datetime import datetime
from flask_login import current_user

# default ns
ns = Namespace("http://www.privacystory.org/ontology#")

# define your namespaces
DPV = Namespace('https://w3id.org/dpv#')
DFLOW = Namespace('http://example.com/ontology/dflow#')
UR = Namespace('http://www.example.org/ur#')
TMC = Namespace('http://www.example.org/tmc#')
MSC = Namespace('http://www.example.org/msc#')

# create a new graph and bind your namespaces
g = Graph()
g.bind('ps', ns)
g.bind('dpv', DPV)
g.bind('dflow', DFLOW)
g.bind('ur', UR)
g.bind('tmc', TMC)
g.bind('msc', MSC)

db = SQLAlchemy()

fictional_project_description = """
Our solution, Camper+, aims to revolutionize camp management by providing you and your customers with the necessary resources to streamline and enhance the camp experience. Camper+ serves as the ultimate toolkit for camp administrators, offering a comprehensive range of tools to simplify the camp setup process. By utilizing Camper+, administrators can efficiently handle tasks ranging from registration to creating nametags. Unlike traditional methods that often involve multiple external sources, Camper+ consolidates all the required information into a single user-friendly platform.

Camper+ caters to three primary user groups, empowering them with specific features:

    Camp administrators: Benefit from scheduling and people management tools that enable seamless enrollment of students, efficient management of enrolled students, and scheduling activities for different camp groups.
    Camp counselors: Access group management tools such as automatic name-tag generators, attendance tracking systems, schedule viewers, and more to facilitate their responsibilities.
    Parents: Utilize our platform to easily register their children for camp, monitor their activities during the camp, and communicate effortlessly with camp administrators and counselors.

For further information, please visit: https://camperapp.herokuapp.com/
"""

fictional_image = "http://data.ifs.tuwien.ac.at/ptm/camperplus.png"


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=False, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean(), default=True)
    has_consented = db.Column(db.Boolean(), default=False)

    def __init__(self, username, email, password, is_active, has_consented):
        self.username = username
        self.email = email
        self.password = password
        self.is_active = is_active
        self.has_consented = has_consented

    def is_active(self):
        return self.is_active

    def has_consented(self):
        return self.has_consented
      
    def get_id(self):
        return self.id

    def is_authenticated(self):
        return True

    def is_anonymous(self):
        return False
      
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    checked_entity = db.Column(db.Boolean, nullable=True)
    checked_quality = db.Column(db.Boolean, nullable=True)
    checked_disclosure = db.Column(db.Boolean, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    stories = db.relationship('Stories', backref='project', lazy=True)
    dfds = db.relationship('Dfd', backref='project', lazy=True)

    def __init__(self, name):
        self.name = name
        self.user_id = current_user.id

    def __repr__(self):
        return "Project %r Created" % self.name
      
    def to_turtle(self):
        g = Graph()
        
        project_individual = URIRef(ns + f"Project_{self.id}")
        g.add((project_individual, ns.id, Literal(f"Project_{self.id}")))
        g.add((project_individual, RDF.type, ns.Project))
        g.add((project_individual, RDFS.label, Literal(self.name)))
        g.add((project_individual, RDFS.comment, Literal(fictional_project_description)))
        g.add((project_individual, FOAF.depiction, URIRef(fictional_image)))
        g.add((project_individual, ns.name, Literal(self.name)))
        
        # Linking stories to project
        for story in self.stories:
            story_individual = URIRef(UR + f"Stories_{story.id}")
            g.add((project_individual, ns.hasStory, story_individual))

        # Linking dfds to project
        for dfd in self.dfds:
            dfd_individual = URIRef(DFLOW + f"DFD_{dfd.id}")
            g.add((project_individual, ns.hasDfd, dfd_individual))

        return g.serialize(format='turtle')

class Stories(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
  story = db.Column(db.String(255), nullable=False)
  disclosure = db.Column(db.Boolean, nullable=True)
  probability_disclosure = db.Column(db.Float, nullable=True)

  entities = db.relationship('Entities', backref='stories', lazy=True)
  quality = db.relationship('StoryQuality', backref='stories', lazy=True)
  triples = db.relationship('Dfd_triple', backref='stories', lazy=True)

  def __init__(self, project_id, story):
    self.project_id = project_id
    self.story = story

  def to_dict(self):
      return {
          'id': self.id,
          'project_id': self.project_id,
          'story': self.story,
          'disclosure': self.disclosure,
          'probability_disclosure': self.probability_disclosure
      }

  def to_turtle(self):
    g = Graph()
    
    story_individual = URIRef(UR + f"Stories_{self.id}")
    
    g.add((story_individual, UR.id, Literal(f"Stories_{self.id}")))
    g.add((story_individual, RDF.type, UR.Stories))
    
    g.add((story_individual, RDFS.comment, Literal(self.story)))

    project_individual = URIRef(ns + f"Project_{self.project_id}")
    g.add((story_individual, UR.Project, project_individual))
  
    g.add((story_individual, UR.story, Literal(self.story)))
    
    
    url_dfd = "s_{}_dfd.png".format(self.id)
    g.add((story_individual, FOAF.depiction, URIRef("http://data.ifs.tuwien.ac.at/ptm/CamperPlus/"+url_dfd)))
    
    
    if self.disclosure is not None:
      g.add((story_individual, UR.disclosure, Literal(self.disclosure)))
    
    if self.probability_disclosure is not None:
      g.add((story_individual, UR.probability_disclosure, Literal(self.probability_disclosure)))
    
    return g.serialize(format='turtle')
  
  def __repr__(self):
    return "Story "%r" Created" % story

class StoryQuality(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  story_id = db.Column(db.Integer, db.ForeignKey('stories.id'), nullable=False)
  story = db.Column(db.String(255), nullable=False)
  kind = db.Column(db.String(1000), nullable=True)
  subkind = db.Column(db.String(1000), nullable=True)
  message = db.Column(db.String(1000), nullable=True)

  def __init__(self, story_id, story, kind, subkind, message):
    self.story_id = story_id
    self.story = story
    self.kind = kind
    self.subkind = subkind
    self.message = message

  
class Entities(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  story_id = db.Column(db.Integer, db.ForeignKey('stories.id'), nullable=False)
  start = db.Column(db.Integer, nullable=False)
  end = db.Column(db.Integer, nullable=False)
  label = db.Column(db.String(255), nullable=False)
  ent_type = db.Column(db.String(255), nullable=False)

  def __init__(self, story_id, start, end, label, ent_type):
    self.story_id = story_id
    self.start = start
    self.end = end
    self.label = label
    self.ent_type = ent_type
    
  def to_dict(self):
        return {
            'id': self.id,
            'story_id': self.story_id,
            'start': self.start,
            'end': self.end,
            'label': self.label,
            'ent_type': self.ent_type
        }
        
  def to_turtle(self):
      g = Graph()
      
      entity_individual = URIRef(Literal(self.label.replace(" ","_")))
      
      g.add((entity_individual, UR.id, Literal(f"Entities_{self.id}")))
      g.add((entity_individual, RDF.type, UR.Entities))
      
      g.add((entity_individual, RDFS.comment, Literal(self.label)))
      g.add((entity_individual, RDFS.label, Literal(self.label)))
      
      story_individual = URIRef(UR + f"Stories_{self.story_id}")
      g.add((entity_individual, UR.basedOnStory, story_individual))
      
      if self.ent_type == "PII":
          g.add((entity_individual, RDF.type, DPV.PersonalData))
          g.add((story_individual, UR.involvesPersonalData, entity_individual))
      elif self.ent_type == "Data Subject":
          g.add((entity_individual, RDF.type, DPV.DataSubject))
          g.add((story_individual, UR.involvesDataSubject, entity_individual))
      elif self.ent_type == "Processing":
          g.add((entity_individual, RDF.type, DPV.Processing))
          g.add((story_individual, UR.involvesProcessing, entity_individual))
      
      g.add((story_individual, UR.hasEntity, entity_individual))

      return g.serialize(format='turtle')
    
  def __repr__(self):
    return "Entitiy "%r" Created" % label

class Dfd(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
  story_ids = db.Column(db.String(2000), nullable=False)
  stories = db.Column(db.String(5000), nullable=False)
  filename = db.Column(db.String(2000), nullable=False)
  date_created = db.Column(db.DateTime, default=datetime.utcnow)

  triple_group = db.relationship('Dfd_triple_group', backref='dfd', lazy=True)

  def __init__(self, project_id, story_ids, stories, filename):
    self.project_id = project_id
    self.story_ids = story_ids
    self.stories = stories
    self.filename = filename
    
  def to_turtle(self):
    g = Graph()

    # Create an individual for the DFD
    dfd_individual = URIRef(DFLOW + f"DFD_{self.id}")
    g.add((dfd_individual, DFLOW.id, Literal(f"DFD_{self.id}")))
    g.add((dfd_individual, RDF.type, DFLOW.Dfd))

    # Add properties
    g.add((dfd_individual, FOAF.depiction, URIRef("http://data.ifs.tuwien.ac.at/ptm/dfd/4/CamperPlus/"+self.filename)))
    g.add((dfd_individual, DFLOW.date_created, Literal(self.date_created)))
    

    project_individual = URIRef(ns + f"Project_{self.project_id}")
    g.add((dfd_individual, DFLOW.fromProject, project_individual))

    for story_id in self.story_ids.split(","):
      story_individual = URIRef(UR + f"Stories {story_id}")
      g.add((story_individual, UR.hasDFD, dfd_individual))
    
    
    return g.serialize(format='turtle')
  
  def __repr__(self):
    return "DFD Created"

class Dfd_triple(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  story_id = db.Column(db.Integer, db.ForeignKey('stories.id'), nullable=False)
  external_entity = db.Column(db.String(2000), nullable=False)
  process = db.Column(db.String(2000), nullable=False)
  data_store = db.Column(db.String(2000), nullable=False)

  requirements = db.relationship('Requirements', backref='dfd_triple', lazy=True, cascade="all, delete-orphan")

  def __init__(self, story_id, external_entity, process, data_store):
    self.story_id = story_id
    self.external_entity = external_entity
    self.process = process
    self.data_store = data_store
    
  def to_dict(self):
      return {
          'id': self.id,
          'story_id': self.story_id,
          'external_entity': self.external_entity,
          'process': self.process,
          'data_store': self.data_store
      }
      
  def to_turtle(self):
    '''
    https://chrdebru.github.io/papers/2019-rcis-preprint.pdf
    
    @base <http://example.org/> .
    @prefix : <http://example.org/> .
    @prefix dfd: <https://w3id.org/dfd#> .

    :Customer a dfd:Interface ;
        rdfs:label "Customer" .

    <http://example.org/Order+Food> a dfd:Process ;
        rdfs:label "Order Food" .

    :Order a dfd:DataFlow ;
        rdfs:label "Order" ;
        dfd:from :Customer ;
        dfd:to <http://example.org/Order+Food> .
    '''

    g = Graph()

    # should be probability of element is dpv entities or not
    some_condition = True
    str_comment = Literal("Data Flow Diagram Element")
    url_dfd = "s_{}_dfd.png".format(self.story_id)

    # DFD Triple as DFD Interface and possibly DPV DataSubject
    # external_entity_individual = URIRef(DFLOW + f"DFD Triple_{self.id}_ExternalEntity")
    external_entity_individual = URIRef(DFLOW + Literal(self.external_entity.replace(" ","_")))

    g.add((external_entity_individual, RDFS.comment, str_comment))
    g.add((external_entity_individual, RDFS.label, Literal(self.external_entity)))
    g.add((external_entity_individual, RDF.type, DFLOW.ExternalEntity))
    g.add((external_entity_individual, FOAF.depiction, URIRef("http://data.ifs.tuwien.ac.at/ptm/CamperPlus/"+url_dfd)))
    
    if some_condition:  # Replace with actual condition
        g.add((external_entity_individual, RDF.type, DPV.DataSubject))

    g.add((external_entity_individual, DFLOW.value, Literal(self.external_entity)))

    # DFD Triple as DFD Process and possibly DPV Processing
    # process_individual = URIRef(DFLOW + f"DFD Triple_{self.id}_Process")
    process_individual = URIRef(DFLOW + Literal(self.process.replace(" ","_")))
 
    g.add((process_individual, RDFS.comment, str_comment))
    g.add((process_individual, RDFS.label, Literal(self.process)))
    g.add((process_individual, RDF.type, DFLOW.Processing))
    if some_condition:  # Replace with actual condition
        g.add((process_individual, RDF.type, DPV.Processing))
    g.add((process_individual, DFLOW.value, Literal(self.process)))
    g.add((process_individual, FOAF.depiction, URIRef("http://data.ifs.tuwien.ac.at/ptm/CamperPlus/"+url_dfd)))

    # DFD Triple as DFD DataStore and possibly DPV PersonalData
    data_store_individual = URIRef(DFLOW + Literal(self.data_store.replace(" ","_")))
    
    g.add((data_store_individual, RDFS.comment, str_comment))
    g.add((data_store_individual, RDFS.label, Literal(self.data_store)))
    g.add((data_store_individual, RDF.type, DFLOW.DataStore))
    if some_condition:  # Replace with actual condition
        g.add((data_store_individual, RDF.type, DPV.PersonalData))
    g.add((data_store_individual, DFLOW.value, Literal(self.data_store)))
    g.add((data_store_individual, FOAF.depiction, URIRef("http://data.ifs.tuwien.ac.at/ptm/CamperPlus/"+url_dfd)))
    
    # create new individual of the class dflow:DataFlow, connecting the ExternalEntity, Processing, and DataStore
    str_dflow_1 = Literal("Source: " + self.external_entity + ", Destination: " + self.process)
    data_flow_node_1 = URIRef(DFLOW + str_dflow_1.replace(" ","_"))
    g.add((data_flow_node_1, RDF.type, DFLOW.DataFlow))
    g.add((data_flow_node_1, RDFS.comment, str_dflow_1))
    g.add((data_flow_node_1, RDFS.label, Literal("DataFlow")))
    g.add((data_flow_node_1, DFLOW.source, external_entity_individual))
    g.add((data_flow_node_1, DFLOW.destination, process_individual))
    
    str_dflow_2 = Literal("Source: " + self.process + ", Destination: " + self.data_store)
    data_flow_node_2 = URIRef(DFLOW + str_dflow_2.replace(" ","_"))
    g.add((data_flow_node_2, RDF.type, DFLOW.DataFlow))
    g.add((data_flow_node_2, RDFS.comment, str_dflow_2))
    g.add((data_flow_node_2, RDFS.label, Literal("DataFlow")))
    g.add((data_flow_node_2, DFLOW.source, process_individual))
    g.add((data_flow_node_2, DFLOW.destination, data_store_individual))

    # Connect the DFD triple parts with the DFD triple
    g.add((external_entity_individual, DFLOW.hasDataFlow, data_flow_node_1))
    g.add((process_individual, DFLOW.hasDataFlow, data_flow_node_1))
    g.add((process_individual, DFLOW.hasDataFlow, data_flow_node_2))
    g.add((data_store_individual, DFLOW.hasDataFlow, data_flow_node_2))
    
    triple_individual = URIRef(DFLOW + f"DFD_Triple_{self.id}")
    g.add((triple_individual, DFLOW.id, Literal(f"DFD_Triple_{self.id}")))
    g.add((triple_individual, DFLOW.hasExternalEntity, external_entity_individual))
    g.add((triple_individual, DFLOW.hasProcess, process_individual))
    g.add((triple_individual, DFLOW.hasDataStore, data_store_individual))
    g.add((triple_individual, DFLOW.hasDataFlow, data_flow_node_1))
    g.add((triple_individual, DFLOW.hasDataFlow, data_flow_node_2))
    
    return g.serialize(format='turtle')
    
class Dfd_triple_group(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  dfd_id = db.Column(db.Integer, db.ForeignKey('dfd.id'), nullable=False)
  external_entity = db.Column(db.String(2000), nullable=False)
  process = db.Column(db.String(2000), nullable=False)
  data_store = db.Column(db.String(2000), nullable=False)

  requirements = db.relationship('RequirementGroup', backref='dfd_triple_group', lazy=True, cascade="all, delete-orphan")

  def __init__(self, dfd_id, external_entity, process, data_store):
    self.dfd_id = dfd_id
    self.external_entity = external_entity
    self.process = process
    self.data_store = data_store
    
  def to_turtle(self):
    '''
    https://chrdebru.github.io/papers/2019-rcis-preprint.pdf
    
    @base <http://example.org/> .
    @prefix : <http://example.org/> .
    @prefix dfd: <https://w3id.org/dfd#> .

    :Customer a dfd:Interface ;
        rdfs:label "Customer" .

    <http://example.org/Order+Food> a dfd:Process ;
        rdfs:label "Order Food" .

    :Order a dfd:DataFlow ;
        rdfs:label "Order" ;
        dfd:from :Customer ;
        dfd:to <http://example.org/Order+Food> .
    '''

    g = Graph()

    # should be probability of element is dpv entities or not
    some_condition = True

    # DFD Triple as DFD Interface and possibly DPV DataSubject
    external_entity_individual = URIRef(DFLOW + f"Dfd_triple_Group{self.id}_ExternalEntity")
    g.add((external_entity_individual, RDF.type, DFLOW.ExternalEntity))
    if some_condition:  # Replace with actual condition
        g.add((external_entity_individual, RDF.type, DPV.DataSubject))
    g.add((external_entity_individual, DFLOW.value, Literal(self.external_entity)))

    # DFD Triple as DFD Process and possibly DPV Processing
    process_individual = URIRef(DFLOW + f"Dfd_triple_Group{self.id}_Process")
    g.add((process_individual, RDF.type, DFLOW.Processing))
    if some_condition:  # Replace with actual condition
        g.add((process_individual, RDF.type, DPV.Processing))
    g.add((process_individual, DFLOW.value, Literal(self.process)))

    # DFD Triple as DFD DataStore and possibly DPV PersonalData
    data_store_individual = URIRef(DFLOW + f"Dfd_triple_Group{self.id}_DataStore")
    g.add((data_store_individual, RDF.type, DFLOW.DataStore))
    if some_condition:  # Replace with actual condition
        g.add((data_store_individual, RDF.type, DPV.PersonalData))
    g.add((data_store_individual, DFLOW.value, Literal(self.data_store)))
    
    # create new individual of the class dflow:DataFlow, connecting the ExternalEntity, Processing, and DataStore
    data_flow_node_1 = BNode()
    g.add((data_flow_node_1, RDF.type, DFLOW.DataFlow))
    g.add((data_flow_node_1, DFLOW.source, external_entity_individual))
    g.add((data_flow_node_1, DFLOW.destination, process_individual))
    
    data_flow_node_2 = BNode()
    g.add((data_flow_node_2, RDF.type, DFLOW.DataFlow))
    g.add((data_flow_node_2, DFLOW.source, process_individual))
    g.add((data_flow_node_2, DFLOW.destination, data_store_individual))

    # Connect the DFD triple parts with the DFD triple
    dfd_triple_individual = URIRef(DFLOW + f"Dfd_triple_Group{self.id}")
    g.add((dfd_triple_individual, DFLOW.hasExternalEntity, external_entity_individual))
    g.add((dfd_triple_individual, DFLOW.hasProcess, process_individual))
    g.add((dfd_triple_individual, DFLOW.hasDataStore, data_store_individual))
    g.add((dfd_triple_individual, DFLOW.hasDataFlow, data_flow_node_1))
    g.add((dfd_triple_individual, DFLOW.hasDataFlow, data_flow_node_2))

    # Connect the DFD parent
    dfd_individual = URIRef(DFLOW + f"DFD_{self.dfd_id}")
    g.add((dfd_triple_individual, DFLOW.dfd_id, dfd_individual))
    g.add((dfd_individual, DFLOW.haveElements, dfd_triple_individual))

    return g.serialize(format='turtle')

class Requirements(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  triple_id = db.Column(db.Integer, db.ForeignKey('dfd_triple.id'), nullable=False)
  req_type = db.Column(db.String(255), nullable=False)
  req_text = db.Column(db.String(2000), nullable=False)
  valid = db.Column(db.String(200), nullable=False, default="no")
  date_created = db.Column(db.DateTime, default=datetime.utcnow)

  def __init__(self, triple_id, req_type, req_text):
    self.triple_id = triple_id
    self.req_type = req_type
    self.req_text = req_text
    
  def to_dict(self):
      return {
          'id': self.id,
          'triple_id': self.triple_id,
          'req_type': self.req_type,
          'req_text': self.req_text,
          'valid': self.valid,
          'date_created': self.date_created.strftime('%m/%d/%Y')
      }
      
  def to_turtle(self):
    g = Graph()
    
    requirement_individual = URIRef(ns + f"Requirements_{self.id}")
    g.add((requirement_individual, RDF.type, ns.Requirements))
    g.add((requirement_individual, ns.id, Literal(f"Requirements_{self.id}")))
    
    g.add((requirement_individual, RDFS.comment, Literal(self.req_text)))
    g.add((requirement_individual, RDFS.label, Literal(self.req_type)))
    
    triple_individual = URIRef(DFLOW + f"DFD_Triple_{self.triple_id}")
    g.add((requirement_individual, DFLOW.triple_id, triple_individual))
    
    g.add((requirement_individual, ns.req_type, Literal(self.req_type)))
    g.add((requirement_individual, ns.req_text, Literal(self.req_text)))

    return g.serialize(format='turtle')
  
class RequirementGroup(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  triple_id = db.Column(db.Integer, db.ForeignKey('dfd_triple_group.id'), nullable=False)
  req_type = db.Column(db.String(255), nullable=False)
  req_text = db.Column(db.String(2000), nullable=False)
  valid = db.Column(db.String(200), nullable=False, default="no")
  date_created = db.Column(db.DateTime, default=datetime.utcnow)

  def __init__(self, triple_id, req_type, req_text):
    self.triple_id = triple_id
    self.req_type = req_type
    self.req_text = req_text

  def to_dict(self):
      return {
          'id': self.id,
          'triple_id': self.triple_id,
          'req_type': self.req_type,
          'req_text': self.req_text,
          'valid': self.valid,
          'date_created': self.date_created.strftime('%m/%d/%Y')
      }


  def to_turtle(self):
    g = Graph()
    
    requirement_individual = URIRef(ns + f"Requirements_Individual{self.id}")
    g.add((requirement_individual, RDF.type, ns.Requirements))

    triple_individual = URIRef(DFLOW + f"DFD Triple_{self.triple_id}")
    g.add((requirement_individual, DFLOW.triple_id, triple_individual))
    
    g.add((requirement_individual, ns.req_type, Literal(self.req_type)))
    g.add((requirement_individual, ns.req_text, Literal(self.req_text)))

    return g.serialize(format='turtle')
      
class LogAction(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50))
    action = db.Column(db.String(50))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    
# define the PrivacyPattern model
class PrivacyPattern(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    summary = db.Column(db.Text)
    context = db.Column(db.Text)
    problem = db.Column(db.Text)
    solution = db.Column(db.Text)
    consequences = db.Column(db.Text)
    examples = db.Column(db.Text)
    see_also = db.Column(db.Text)
    general_comments = db.Column(db.Text)

    # define relationship with Category
    category_id = db.Column(db.Integer, db.ForeignKey('pattern_category.id'))
    category = db.relationship('PatternCategory', backref=db.backref('privacy_patterns', lazy=True))

    # define relationship with related patterns (self referencing)
    parent_id = db.Column(db.Integer, db.ForeignKey('privacy_pattern.id'))
    related_patterns = db.relationship('PrivacyPattern', backref=db.backref('parent', remote_side=[id]))

    # Association tables defined in class
    requirements = db.relationship('Requirements',
                                   secondary='requirements_patterns',
                                   backref=db.backref('privacy_patterns', lazy='dynamic'))

    requirement_groups = db.relationship('RequirementGroup',
                                         secondary='requirement_groups_patterns',
                                         backref=db.backref('privacy_patterns', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'summary': self.summary,
            'context': self.context,
            'problem': self.problem,
            'solution': self.solution,
            'consequences': self.consequences,
            'examples': self.examples,
            'see_also': self.see_also,
            'general_comments': self.general_comments,
            'category_id': self.category_id,
            'parent_id': self.parent_id
        }
        
    def to_turtle(self):
      g = Graph()
      n = Namespace(ns)
      
      pattern_individual = URIRef(n + f"PrivacyPattern_{self.id}")
      g.add((pattern_individual, RDF.type, n.PrivacyPattern))

      g.add((pattern_individual, n.id, f"PrivacyPattern_{self.id}"))
      g.add((pattern_individual, n.summary, Literal(self.summary)))
      #... add other properties in similar way

      return g.serialize(format='turtle')
    
      # The relationships (requirements, requirement_groups, category, and related_patterns) in the PrivacyPattern class aren't included in the Turtle representation. If you want to represent these relationships, you could add triples like:
      
      # g.add((pattern_individual, n.hasRequirement, requirement_individual))
      # g.add((pattern_individual, n.hasRequirementGroup, group_individual))
      # g.add((pattern_individual, n.hasCategory, category_individual))
      # g.add((pattern_individual, n.hasRelatedPattern, related_pattern_individual))

        
# Association tables defined as separate models
class RequirementsPatterns(db.Model):
    requirement_id = db.Column(db.Integer, db.ForeignKey('requirements.id'), primary_key=True)
    privacy_pattern_id = db.Column(db.Integer, db.ForeignKey('privacy_pattern.id'), primary_key=True)
    
    def to_dict(self):
        return {
            'requirement_id': self.requirement_id,
            'privacy_pattern_id': self.privacy_pattern_id
        }

class RequirementGroupsPatterns(db.Model):
    requirement_group_id = db.Column(db.Integer, db.ForeignKey('requirement_group.id'), primary_key=True)
    privacy_pattern_id = db.Column(db.Integer, db.ForeignKey('privacy_pattern.id'), primary_key=True)
        
    def to_dict(self):
        return {
            'requirement_group_id': self.requirement_group_id,
            'privacy_pattern_id': self.privacy_pattern_id
        }

# define the Category model
class PatternCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name
        }

    def to_turtle(self):
        g = Graph()
        n = Namespace(ns)

        # Create an individual for the category
        category_individual = URIRef(n + f"PatternCategory_{self.id}")
        g.add((category_individual, RDF.type, n.PatternCategory))

        # Add properties
        g.add((category_individual, n.id, f"PatternCategory_{self.id}"))
        g.add((category_individual, n.name, Literal(self.name)))

        return g.serialize(format='turtle')


    