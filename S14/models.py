
# Файл `models.py`

from contextlib import asynccontextmanager
from peewee import SqliteDatabase, Model, IntegerField, CharField, FloatField
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List

# ==================== БАЗА ДАННЫХ ====================
db = SqliteDatabase('workload.db')

class Workload(Model):
    """Модель нагрузки преподавателя"""
    teacher_id = IntegerField(null=False, verbose_name="ID преподавателя")
    discipline = CharField(max_length=200, null=False, verbose_name="Дисциплина")
    hours_per_week = FloatField(null=False, verbose_name="Часов в неделю")
    groups_count = IntegerField(null=False, verbose_name="Количество групп")
    semester = IntegerField(null=False, verbose_name="Семестр (1 или 2)")
    year = IntegerField(null=False, verbose_name="Учебный год")
    total_hours = FloatField(null=False, verbose_name="Общая нагрузка за семестр")
    notes = CharField(max_length=500, null=True, verbose_name="Примечания")

    class Meta:
        database = db
        table_name = 'workloads'

def calculate_total_hours(hours_per_week: float, groups_count: int) -> float:
    """Расчет общей нагрузки за семестр (18 недель)"""
    WEEKS_IN_SEMESTER = 18
    return round(hours_per_week * groups_count * WEEKS_IN_SEMESTER, 2)

def init_db():
    """Функция инициализации базы данных"""
    db.connect()
    db.create_tables([Workload], safe=True)
    db.close()

# ==================== СХЕМЫ PYDANTIC ====================
class WorkloadCreate(BaseModel):
    """Схема для создания нагрузки"""
    teacher_id: int = Field(..., gt=0, description="ID преподавателя")
    discipline: str = Field(..., max_length=200, description="Название дисциплины")
    hours_per_week: float = Field(..., ge=1, le=54, description="Часов в неделю (1-54)")
    groups_count: int = Field(..., ge=1, le=10, description="Количество групп (1-10)")
    semester: int = Field(..., ge=1, le=2, description="Семестр (1 или 2)")
    year: int = Field(..., ge=2020, le=2030, description="Учебный год")
    notes: Optional[str] = Field(None, max_length=500, description="Примечания")

class WorkloadUpdate(BaseModel):
    """Схема для обновления нагрузки"""
    hours_per_week: Optional[float] = Field(None, ge=1, le=54, description="Часов в неделю")
    groups_count: Optional[int] = Field(None, ge=1, le=10, description="Количество групп")
    notes: Optional[str] = Field(None, max_length=500, description="Примечания")

class WorkloadOut(BaseModel):
    """Схема для ответа (вывода) нагрузки"""
    id: int
    teacher_id: int
    discipline: str
    hours_per_week: float
    groups_count: int
    semester: int
    year: int
    total_hours: float
    notes: Optional[str]

# ==================== LIFESPAN ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    print("🚀 Запуск сервера Workload Service...")
    init_db()
    print("✅ База данных инициализирована")
    yield
    print("🛑 Остановка сервера...")
    if not db.is_closed():
        db.close()
    print("✅ Ресурсы освобождены")

# ==================== FASTAPI ПРИЛОЖЕНИЕ ====================
app = FastAPI(
    title="Workload Calculation Service",
    description="Сервис расчета нагрузки преподавателя",
    version="1.0",
    lifespan=lifespan
)

# ==================== ЭНДПОИНТЫ ====================
@app.post("/workloads", response_model=WorkloadOut, status_code=201)
def create_workload(workload: WorkloadCreate):
    """Создание записи нагрузки"""
    try:
        db.connect()
        with db.atomic():
            # Проверка уникальности
            if Workload.select().where(
                (Workload.teacher_id == workload.teacher_id) &
                (Workload.discipline == workload.discipline) &
                (Workload.semester == workload.semester) &
                (Workload.year == workload.year)
            ).exists():
                raise HTTPException(400, "Такая нагрузка уже существует")
            
            total_hours = calculate_total_hours(workload.hours_per_week, workload.groups_count)
            
            new_workload = Workload.create(
                teacher_id=workload.teacher_id,
                discipline=workload.discipline,
                hours_per_week=workload.hours_per_week,
                groups_count=workload.groups_count,
                semester=workload.semester,
                year=workload.year,
                total_hours=total_hours,
                notes=workload.notes
            )
        return new_workload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Ошибка при создании: {str(e)}")
    finally:
        db.close()

@app.put("/workloads/{workload_id}", response_model=WorkloadOut)
def update_workload(workload_id: int, workload: WorkloadUpdate):
    """Обновление информации о нагрузке"""
    try:
        db.connect()
        with db.atomic():
            existing = Workload.get_or_none(Workload.id == workload_id)
            if not existing:
                raise HTTPException(404, "Нагрузка не найдена")
            
            update_data = {}
            new_hours = existing.hours_per_week
            new_groups = existing.groups_count
            
            if workload.hours_per_week is not None:
                update_data['hours_per_week'] = workload.hours_per_week
                new_hours = workload.hours_per_week
            if workload.groups_count is not None:
                update_data['groups_count'] = workload.groups_count
                new_groups = workload.groups_count
            if workload.notes is not None:
                update_data['notes'] = workload.notes
            
            if workload.hours_per_week is not None or workload.groups_count is not None:
                update_data['total_hours'] = calculate_total_hours(new_hours, new_groups)
            
            if update_data:
                Workload.update(update_data).where(Workload.id == workload_id).execute()
            
            updated = Workload.get_by_id(workload_id)
        return updated
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Ошибка при обновлении: {str(e)}")
    finally:
        db.close()

@app.delete("/workloads/{workload_id}")
def delete_workload(workload_id: int):
    """Удаление нагрузки"""
    try:
        db.connect()
        with db.atomic():
            deleted = Workload.delete().where(Workload.id == workload_id).execute()
        return {"deleted": bool(deleted), "message": "Нагрузка удалена" if deleted else "Нагрузка не найдена"}
    except Exception as e:
        raise HTTPException(500, f"Ошибка при удалении: {str(e)}")
    finally:
        db.close()

@app.get("/workloads/{workload_id}", response_model=WorkloadOut)
def get_workload(workload_id: int):
    """Получение нагрузки по ID"""
    try:
        db.connect()
        workload = Workload.get_or_none(Workload.id == workload_id)
        if not workload:
            raise HTTPException(404, "Нагрузка не найдена")
        return workload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Ошибка при получении: {str(e)}")
    finally:
        db.close()

@app.get("/workloads", response_model=List[WorkloadOut])
def list_workloads(
    teacher_id: Optional[int] = None,
    discipline: Optional[str] = None,
    semester: Optional[int] = None,
    year: Optional[int] = None,
    min_hours: Optional[float] = None,
    max_hours: Optional[float] = None,
    min_total: Optional[float] = None,
    max_total: Optional[float] = None,
    limit: int = 100,
    offset: int = 0
):
    """Получение списка нагрузки с фильтрацией"""
    try:
        db.connect()
        query = Workload.select()
        
        if teacher_id:
            query = query.where(Workload.teacher_id == teacher_id)
        if discipline:
            query = query.where(Workload.discipline.contains(discipline))
        if semester:
            query = query.where(Workload.semester == semester)
        if year:
            query = query.where(Workload.year == year)
        if min_hours is not None:
            query = query.where(Workload.hours_per_week >= min_hours)
        if max_hours is not None:
            query = query.where(Workload.hours_per_week <= max_hours)
        if min_total is not None:
            query = query.where(Workload.total_hours >= min_total)
        if max_total is not None:
            query = query.where(Workload.total_hours <= max_total)
        
        return list(query.offset(offset).limit(limit))
    except Exception as e:
        raise HTTPException(500, f"Ошибка при получении списка: {str(e)}")
    finally:
        db.close()

@app.get("/teachers/{teacher_id}/workload", response_model=List[WorkloadOut])
def get_teacher_workload(teacher_id: int):
    """Получение всей нагрузки преподавателя"""
    try:
        db.connect()
        workloads = list(Workload.select().where(Workload.teacher_id == teacher_id))
        return workloads
    except Exception as e:
        raise HTTPException(500, f"Ошибка при получении: {str(e)}")
    finally:
        db.close()

@app.get("/calculate/semester/{year}/{semester}")
def calculate_semester_load(year: int, semester: int):
    """Расчёт общей нагрузки за семестр"""
    try:
        db.connect()
        workloads = Workload.select().where(
            (Workload.year == year) & (Workload.semester == semester)
        )
        
        total_load = sum(w.total_hours for w in workloads)
        
        return {
            "year": year,
            "semester": semester,
            "total_hours": total_load,
            "teachers_count": workloads.count(),
            "details": list(workloads)
        }
    except Exception as e:
        raise HTTPException(500, f"Ошибка при расчёте: {str(e)}")
    finally:
        db.close()

@app.get("/")
def root():
    """Корневой эндпоинт"""
    return {
        "service": "Workload Calculation Service",
        "version": "1.0",
        "description": "Сервис расчета нагрузки преподавателя",
        "formula": "total_hours = hours_per_week × groups_count × 18 недель",
        "endpoints": {
            "POST /workloads": "Создать нагрузку",
            "GET /workloads": "Список нагрузки",
            "GET /workloads/{id}": "Получить нагрузку по ID",
            "PUT /workloads/{id}": "Обновить нагрузку",
            "DELETE /workloads/{id}": "Удалить нагрузку",
            "GET /teachers/{id}/workload": "Нагрузка преподавателя",
            "GET /calculate/semester/{year}/{semester}": "Расчёт за семестр"
        }
    }

# ==================== ТОЧКА ВХОДА ====================
if __name__ == "__main__":
    import uvicorn
    print("=" * 50)
    print("Запуск сервера Workload Calculation Service...")
    print("Документация API: http://localhost:8003/docs")
    print("Формула расчета: total_hours = hours_per_week × groups_count × 18")
    print("=" * 50)
    uvicorn.run(app, host="127.0.0.1", port=8003)