from fastapi import FastAPI, HTTPException, Query, Path
from typing import List, Optional
from models import Evento, Participante
from database import container
from azure.cosmos import exceptions
from datetime import datetime

app = FastAPI(title="API de Gestión de Eventos y Participantes", version="1.0.0")

# ----------------------------
# Endpoints para Eventos
# ----------------------------

@app.post("/events/", response_model=Evento, status_code=201)
def create_event(event: Evento):

    try:
        container.create_item(body=event.dict())
        return event
    except exceptions.CosmosResourceExistsError:
        raise HTTPException(status_code=400, detail="El evento con este ID ya existe.")
    except exceptions.CosmosHttpResponseError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/events/{event_id}", response_model=Evento)
def get_event(event_id: str = Path(..., description="ID del evento a recuperar")):
    try:
        event = container.read_item(item=event_id, partition_key=event_id)
        return event
    except exceptions.CosmosResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")
    except exceptions.CosmosHttpResponseError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/events/", response_model=List[Evento])
def list_events(
    date: Optional[str] = Query(None, description="Filtrar eventos por fecha específica (YYYY-MM-DD)"),
    location: Optional[str] = Query(None, description="Filtrar eventos por ubicación"),
    sort_by: Optional[str] = Query(None, description="Ordenar por 'date' o 'name'"),
    order: Optional[str] = Query("asc", description="Orden ascendente 'asc' o descendente 'desc'")
):
    try:
        query = "SELECT * FROM c WHERE 1=1"
        params = []
        
        if date:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d")
                query += " AND STARTSWITH(c.date, @date)"
                params.append({"name": "@date", "value": date_obj.strftime("%Y-%m-%d")})
            except ValueError:
                raise HTTPException(status_code=400, detail="Formato de fecha inválido. Use YYYY-MM-DD.")
        
        if location:
            query += " AND c.location = @location"
            params.append({"name": "@location", "value": location})
        
        if sort_by in ["date", "name"]:
            query += f" ORDER BY c.{sort_by} {order.upper()}"
        
        items = list(container.query_items(query=query, parameters=params, enable_cross_partition_query=True))
        return items
    except exceptions.CosmosHttpResponseError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/events/{event_id}", response_model=Evento)
def update_event(event_id: str, updated_event: Evento):
    try:
        existing_event = container.read_item(item=event_id, partition_key=event_id)
        
        print(updated_event.dict(exclude_unset=True))
        # Actualizar campos
        existing_event.update(updated_event.dict(exclude_unset=True))
        
        print(existing_event)
        # Validar capacidad
        if existing_event['capacity'] < len(existing_event['participants']):
            raise HTTPException(status_code=400, detail="La capacidad no puede ser menor que el número de participantes actuales.")
        
        container.replace_item(item=event_id, body=existing_event)
        return existing_event
    except exceptions.CosmosResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")
    except exceptions.CosmosHttpResponseError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/events/{event_id}", status_code=204)
def delete_event(event_id: str):
    try:
        container.delete_item(item=event_id, partition_key=event_id)
        return
    except exceptions.CosmosResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")
    except exceptions.CosmosHttpResponseError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Endpoints para Participantes
# ----------------------------

@app.post("/events/{event_id}/participants/", response_model=Participante, status_code=201)
def add_participant(event_id: str, participant: Participante):
    try:
        event = container.read_item(item=event_id, partition_key=event_id)
        
        # Validar capacidad
        if len(event['participants']) >= event['capacity']:
            raise HTTPException(status_code=400, detail="Capacidad del evento alcanzada.")
        
        # Verificar si el participante ya existe
        if any(p['id'] == participant.id for p in event['participants']):
            raise HTTPException(status_code=400, detail="El participante con este ID ya está inscrito.")
        
        # Agregar participante
        event['participants'].append(participant.dict())
        container.replace_item(item=event_id, body=event)
        return participant
    except exceptions.CosmosResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")
    except exceptions.CosmosHttpResponseError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/events/{event_id}/participants/{participant_id}", response_model=Participante)
def get_participant(event_id: str, participant_id: str):
    try:
        event = container.read_item(item=event_id, partition_key=event_id)
        participant = next((p for p in event['participants'] if p['id'] == participant_id), None)
        if participant:
            return participant
        else:
            raise HTTPException(status_code=404, detail="Participante no encontrado.")
    except exceptions.CosmosResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")
    except exceptions.CosmosHttpResponseError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/events/{event_id}/participants/", response_model=List[Participante])
def list_participants(
    event_id: str,
    name: Optional[str] = Query(None, description="Filtrar participantes por nombre"),
    email: Optional[str] = Query(None, description="Filtrar participantes por correo electrónico"),
    sort_by: Optional[str] = Query(None, description="Ordenar por 'name' o 'registration_date'"),
    order: Optional[str] = Query("asc", description="Orden ascendente 'asc' o descendente 'desc'")
):
    try:
        event = container.read_item(item=event_id, partition_key=event_id)
        participants = event.get('participants', [])
        
        if name:
            participants = [p for p in participants if name.lower() in p['name'].lower()]
        
        if email:
            participants = [p for p in participants if email.lower() in p['email'].lower()]
        
        if sort_by in ["name", "registration_date"]:
            reverse = True if order.lower() == "desc" else False
            participants.sort(key=lambda x: x[sort_by], reverse=reverse)
        
        return participants
    except exceptions.CosmosResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/events/{event_id}/participants/{participant_id}", response_model=Participante)
def update_participant(event_id: str, participant_id: str, updated_participant: Participante):
    try:
        event = container.read_item(item=event_id, partition_key=event_id)
        participant = next((p for p in event['participants'] if p['id'] == participant_id), None)
        
        if not participant:
            raise HTTPException(status_code=404, detail="Participante no encontrado.")
        
        # Actualizar campos
        participant.update(updated_participant.dict(exclude_unset=True))
        
        # Reemplazar el participante en la lista
        event['participants'] = [p if p['id'] != participant_id else participant for p in event['participants']]
        container.replace_item(item=event_id, body=event)
        return participant
    except exceptions.CosmosResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")
    except exceptions.CosmosHttpResponseError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete("/events/{event_id}/participants/{participant_id}", status_code=204)
def delete_participant(event_id: str, participant_id: str):
    try:
        event = container.read_item(item=event_id, partition_key=event_id)
        participant = next((p for p in event['participants'] if p['id'] == participant_id), None)
        
        if not participant:
            raise HTTPException(status_code=404, detail="Participante no encontrado.")
        
        # Eliminar participante
        event['participants'] = [p for p in event['participants'] if p['id'] != participant_id]
        container.replace_item(item=event_id, body=event)
        return
    except exceptions.CosmosResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Evento no encontrado.")
    except exceptions.CosmosHttpResponseError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ----------------------------
# Endpoints para Reportes (Opcional)
# ----------------------------

@app.get("/reports/participants-count/", response_model=List[dict])
def participants_count():
    try:
        query = """
        SELECT c.id as event_id, c.name, ARRAY_LENGTH(c.participants) as participants_count
        FROM c
        """
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        return items
    except exceptions.CosmosHttpResponseError as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8080)))