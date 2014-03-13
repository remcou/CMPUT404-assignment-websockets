#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2014 Remco Uittenbogerd
# Copyright (c) 2013-2014 Abram Hindle
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request, redirect, url_for, make_response
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True

class Client:
    def __init__(self):
        self.queue = queue.Queue()

    def put(self, v):
        self.queue.put_nowait(v)

    def get(self):
        return self.queue.get()

class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()
        
    def add_listener(self, listener):
        self.listeners.append( listener )
        listener.put( json.dumps( { "world": self.space } ) )

    def remove_listener(self, listener):
        self.listeners.remove( listener )

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        #self.update_listeners( entity ) Don't update right now, otherwise we will be updating 5 times per entity!

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners( entity )

    def update_listeners_entity(self, entity):
        update = dict()
        update[entity] = self.space[entity]
        for listener in self.listeners:
            #listener.put( json.dumps(self.space) )
            listener.put( json.dumps( update ) )

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())
    
    def world(self):
        return self.space

myWorld = World()        


#def set_listener( entity, data ):
#    ''' do something with the update ! '''

#myWorld.add_set_listener( set_listener )

# Data it reads:
# { entry_id: { key: value, key: value, key etc....} }
def read_ws(ws,client):
    try:
        while True:
            msg = ws.receive()
            if (msg is not None):
                packet = json.loads(msg)
                for entityName, newValue in packet.iteritems():
                    for key, value in newValue.iteritems():
                        myWorld.update( entityName, key, value )
                    myWorld.update_listeners_entity(entityName)
            else:
                break
    except:
        '''Done'''

@sockets.route('/subscribe')
def subscribe_socket(ws):
    client = Client()
    myWorld.add_listener( client )
    g = gevent.spawn( read_ws, ws, client )
    try:
        while True:
            # block here
            msg = client.get()
            ws.send(msg)
    except Exception as e:# WebSocketError as e:
        print "WS Error %s" % e
    finally:
        myWorld.remove_listener( client )
        gevent.kill(g)


def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data != ''):
        return json.loads(request.data)
    else:
        return json.loads(request.form.keys()[0])

def world_response():
    data = json.dumps(myWorld.world())
    response = make_response(data)
    response.headers['Content-Type'] = 'application/json'
    return response

def entity_response( entity ):
    data = json.dumps(myWorld.get( entity ))
    response = make_response(data)
    response.headers['Content-Type'] = 'application/json'
    return response

@app.route("/")
def hello():
    return redirect('/static/index.html')

@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    data = flask_post_json()
    for key, value in data.iteritems():
        myWorld.update( entity, key, value )

    return entity_response( entity )

@app.route("/world", methods=['POST','GET'])
def world():
    return world_response()

@app.route("/entity/<entity>")
def get_entity(entity):
    return entity_response( entity )

@app.route("/clear", methods=['POST','GET'])
def clear():
    myWorld.clear()
    return world_response()

if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
