import random

ANIMALS = [
    "고양이", 
    "오징어", 
    "펭귄", 
    "불타는 고라니", 
    "투명한 개구리"
]

HUMANS = [
    "잠에서 덜 깬 유튜버", 
    "눈이 네 개인 할머니", 
    "머리에 우유팩 쓴 소년"
]

BACKGROUNDS = [
    "트랄라레로 트랄랄라 세계", 
    "비눗방울로 만든 지하철", 
    "녹아내리는 놀이공원"
]

DANCES = [
    "퉁퉁퉁 사후르 댄스", 
    "삐걱삐걱 박수춤", 
    "무중력 발차기"
]

ACTIONS = [
    "울기 시작함", 
    "공중에서 뒤집힘", 
    "무언가를 집어삼킴", 
    "의자를 던짐", 
    "모든 걸 잊어버림"
]

def generate_dynamic_prompt() -> str:
    animal = random.choice(ANIMALS)
    human = random.choice(HUMANS)
    background = random.choice(BACKGROUNDS)
    dance = random.choice(DANCES)
    action = random.choice(ACTIONS)

    return (
        f"Write a cursed micro-story (max 3 sentences) set in {background}, "
        f"where a {animal} and a {human} perform the {dance}. "
        f"The story should feature surreal emotional twists and chaotic events—"
        f"like when someone suddenly {action}. "
        f"End with a haunting image. No logic, no numbers. Only vibes."
    )
