import couchdb
import uuid
import tkinter as tk
from tkinter import messagebox, Toplevel, Label, Button, Entry, StringVar, OptionMenu, Frame
import random
import json
from datetime import datetime

# Configuração do CouchDB
USER = ""
PASSWORD = ""
COUCHDB_URL = f"http://{USER}:{PASSWORD}@127.0.0.1:5984/"
couch = couchdb.Server(COUCHDB_URL)

DB_NAME = "battle_game"
CHARACTER_DB_NAME = "characters"

if DB_NAME not in couch:
    couch.create(DB_NAME)
if CHARACTER_DB_NAME not in couch:
    couch.create(CHARACTER_DB_NAME)

db = couch[DB_NAME]
character_db = couch[CHARACTER_DB_NAME]

# Criação de um design document com uma view para melhorar a consulta dos personagens
DESIGN_DOC_ID = "_design/characters"
if DESIGN_DOC_ID not in character_db:
    design_doc = {
        "_id": DESIGN_DOC_ID,
        "views": {
            "by_name": {
                "map": "function(doc) { if(doc.name) { emit(doc.name, null); } }"
            }
        }
    }
    character_db.save(design_doc)
    print("[INFO] Design document 'characters/by_name' criado com sucesso.")
else:
    print("[INFO] Design document 'characters/by_name' já existe.")

def create_character(name):
    if not name:
        return
    char_data = {
        "_id": str(uuid.uuid4()),
        "name": name,
        "level": 1,
        "experience": 0,
        "wins": 0,       # Contador de vitórias
        "health": 100,
        "attack": 10,
        "defense": 5,
        "magic": 8       # Valor padrão para magia
    }
    character_db.save(char_data)
    update_character_menu()

def read_characters():
    """
    Retorna uma lista de tuplas (doc_id, nome) utilizando a view 'by_name'.
    Essa abordagem é mais eficiente que iterar por todos os documentos.
    """
    result = character_db.view("characters/by_name", include_docs=True)
    return [(row.doc["_id"], row.doc["name"]) for row in result]

def update_character_menu():
    """
    Atualiza o OptionMenu com a lista de personagens disponíveis.
    """
    characters = [name for _, name in read_characters()]
    if characters:
        char_var.set(characters[0])
        char_menu['menu'].delete(0, 'end')
        for char in characters:
            char_menu['menu'].add_command(
                label=char,
                command=lambda c=char: char_var.set(c)
            )
    else:
        char_var.set("Nenhum personagem")
        char_menu['menu'].delete(0, 'end')
        char_menu['menu'].add_command(
            label="Nenhum personagem",
            command=lambda: char_var.set("Nenhum personagem")
        )

def detail_character():
    """
    Exibe os detalhes do personagem selecionado em uma nova janela.
    """
    selected_name = char_var.get()
    doc = next((character_db[c] for c, name in read_characters() if name == selected_name), None)
    if not doc:
        messagebox.showerror("Erro", "Nenhum personagem selecionado ou não encontrado.")
        return

    detail_window = Toplevel(root)
    detail_window.title("Detalhes do Personagem")
    Label(detail_window, text=f"Nome: {doc['name']}").pack()
    Label(detail_window, text=f"Nível: {doc['level']}").pack()
    Label(detail_window, text=f"Experiência: {doc['experience']}").pack()
    Label(detail_window, text=f"Vitórias: {doc.get('wins', 0)}").pack()
    Label(detail_window, text=f"Vida (HP): {doc['health']}").pack()
    Label(detail_window, text=f"Ataque: {doc['attack']}").pack()
    Label(detail_window, text=f"Defesa: {doc['defense']}").pack()
    Label(detail_window, text=f"Magia: {doc.get('magic', 8)}").pack()

def delete_character():
    """
    Exclui o personagem selecionado, após confirmação do usuário.
    """
    selected_name = char_var.get()
    doc_id = next((c for c, name in read_characters() if name == selected_name), None)
    if not doc_id:
        messagebox.showerror("Erro", "Nenhum personagem selecionado ou não encontrado.")
        return

    if messagebox.askyesno("Confirmar Exclusão", f"Tem certeza que deseja excluir o personagem '{selected_name}'?"):
        character_db.delete(character_db[doc_id])
        update_character_menu()
        messagebox.showinfo("Excluído", f"O personagem '{selected_name}' foi excluído.")

def generate_bot(player):
    """
    Gera um bot com base nos status atuais do jogador.
    O fator de dificuldade varia conforme o nível:
      - Níveis 1 a 4: 0.95
      - Níveis 5 a 9: 1.0
      - Níveis 10 a 14: 1.05
      - Níveis 15+: 1.1
    """
    level = player["level"]
    if level < 5:
        factor = 0.95
    elif level < 10:
        factor = 1.0
    elif level < 15:
        factor = 1.05
    else:
        factor = 1.1

    bot = {
        "name": f"Bot Nível {level}",
        "level": level,
        "health": int(player["health"] * factor),
        "attack": int(player["attack"] * factor),
        "defense": int(player["defense"] * factor),
        "magic": int(player.get("magic", 8) * factor)
    }
    print(f"[DEBUG] Bot gerado: {bot}")
    return bot

def bot_action():
    """Define aleatoriamente qual ação o bot irá tomar no turno dele."""
    action = random.choice(["attack", "defend", "magic"])
    print(f"[DEBUG] Bot escolheu: {action}")
    return action

def compute_damage(attacker, defender, action):
    """
    Calcula o dano que 'attacker' causaria em 'defender' com base na ação.
    Se o dano base for positivo, garante que o dano mínimo seja 1.
    Não atualiza os HP.
    """
    if action == "attack":
        base_damage = attacker.get("attack", 10) - defender.get("defense", 5)
    elif action == "magic":
        base_damage = attacker.get("magic", 8) - defender.get("defense", 5)
    else:
        base_damage = 0

    if defender.get("selected_action") == "defend":
        base_damage //= 2

    damage = max(base_damage, 1) if base_damage > 0 else 0
    print(f"[DEBUG] {attacker.get('name', 'Atacante')} usando {action} causa {damage} de dano (base: {base_damage}) em {defender.get('name', 'Defensor')}")
    return damage

def battle_turn(player, enemy, battle_window, player_hp_label, enemy_hp_label, player_action):
    """
    Executa um turno de batalha de forma SIMULTÂNEA:
      - Calcula e aplica os danos do jogador e do bot.
      - Atualiza os rótulos de HP.
      - Verifica as condições de vitória.
    """
    player["name"] = player.get("name", "Jogador")
    enemy["name"] = enemy.get("name", "Bot")

    player["selected_action"] = player_action
    enemy_act = bot_action()
    enemy["selected_action"] = enemy_act

    damage_to_enemy = compute_damage(player, enemy, player["selected_action"])
    damage_to_player = compute_damage(enemy, player, enemy_act)

    enemy["health"] -= damage_to_enemy
    player["health"] -= damage_to_player

    player_hp_label.config(text=f"HP: {player['health']}")
    enemy_hp_label.config(text=f"HP: {enemy['health']}")

    if player["health"] <= 0 and enemy["health"] <= 0:
        messagebox.showinfo("Resultado", "Empate!")
        battle_window.destroy()
        return
    elif player["health"] <= 0:
        messagebox.showinfo("Resultado", f"{enemy['name']} venceu!")
        battle_window.destroy()
        return
    elif enemy["health"] <= 0:
        messagebox.showinfo("Resultado", f"{player['name']} venceu!")
        player["wins"] = player.get("wins", 0) + 1
        xp_gained = random.randint(10, 20)
        player["experience"] += xp_gained
        messagebox.showinfo("XP", f"Você ganhou {xp_gained} de experiência!")
        level_ups = 0
        while player["experience"] >= 20:
            player["experience"] -= 20
            player["level"] += 1
            level_ups += 1
            player["attack"] += 5
            player["defense"] += 5
            player["magic"] = player.get("magic", 8) + 5
            player["health"] += 5
        if level_ups > 0:
            messagebox.showinfo("Level Up!",
                                f"{player['name']} subiu {level_ups} nível(is)!\n"
                                f"Agora está no nível {player['level']} e ganhou +5 em cada atributo.")
        character_db.save(player)

        if messagebox.askyesno("Continuar", "Deseja continuar batalhando?"):
            new_bot = generate_bot(player)
            enemy.clear()
            enemy.update(new_bot)
            enemy_hp_label.config(text=f"HP: {enemy['health']}")
            return
        else:
            battle_window.destroy()
            return

def start_battle_versus_bot():
    """
    Inicia a tela de batalha contra o bot, exibindo as informações do jogador e do bot,
    além das opções de ataque.
    """
    battle_window = Toplevel(root)
    battle_window.title("Batalha contra Bot")

    player_name = char_var.get()
    player_data = next((character_db[c] for c, name in read_characters() if name == player_name), None)
    if not player_data:
        messagebox.showerror("Erro", "Selecione um personagem válido.")
        return

    bot_data = generate_bot(player_data)

    top_frame = Frame(battle_window)
    top_frame.pack(pady=10)

    player_frame = Frame(top_frame, bd=2, relief="solid", padx=10, pady=10)
    player_frame.pack(side="left", padx=20)
    Label(player_frame, text=f"{player_data['name']} (Lv {player_data['level']})",
          font=("Helvetica", 12, "bold")).pack()
    player_hp_label = Label(player_frame, text=f"HP: {player_data['health']}", font=("Helvetica", 10))
    player_hp_label.pack()

    enemy_frame = Frame(top_frame, bd=2, relief="solid", padx=10, pady=10)
    enemy_frame.pack(side="right", padx=20)
    Label(enemy_frame, text=f"{bot_data['name']} (Lv {bot_data['level']})",
          font=("Helvetica", 12, "bold")).pack()
    enemy_hp_label = Label(enemy_frame, text=f"HP: {bot_data['health']}", font=("Helvetica", 10))
    enemy_hp_label.pack()

    mid_label = Label(battle_window, text="O que você vai fazer?", font=("Helvetica", 12))
    mid_label.pack(pady=10)

    actions_frame = Frame(battle_window)
    actions_frame.pack(pady=5)

    def player_choice(action):
        battle_turn(player_data, bot_data, battle_window, player_hp_label, enemy_hp_label, action)

    Button(actions_frame, text="Atacar", width=10, command=lambda: player_choice("attack")).pack(side="left", padx=5)
    Button(actions_frame, text="Magia", width=10, command=lambda: player_choice("magic")).pack(side="left", padx=5)
    Button(actions_frame, text="Defender", width=10, command=lambda: player_choice("defend")).pack(side="left", padx=5)

# Função de Backup: salva os dados do banco de personagens em um arquivo JSON
def backup_database():
    backup_data = []
    for doc_id in character_db:
        backup_data.append(dict(character_db[doc_id]))
    backup_filename = f"characters_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(backup_filename, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, ensure_ascii=False, indent=4)
        print(f"[INFO] Backup realizado com sucesso: {backup_filename}")
    except Exception as e:
        print(f"[ERROR] Falha ao realizar backup: {e}")

# Função para agendar backups automáticos (ex.: a cada 5 minutos = 300000 ms)
def schedule_backup():
    backup_database()
    root.after(300000, schedule_backup)  # 300000 ms = 5 minutos

# Janela principal
root = tk.Tk()
root.title("Jogo de Batalha por Turnos")

Label(root, text="Nome do Personagem:").pack()
char_entry = Entry(root, width=30)
char_entry.pack()
Button(root, text="Criar Personagem", command=lambda: create_character(char_entry.get())).pack(pady=5)

Label(root, text="Personagens Disponíveis:").pack()
characters = [name for _, name in read_characters()]
char_var = StringVar(root)
char_var.set(characters[0] if characters else "Nenhum personagem")
char_menu = OptionMenu(root, char_var, *(characters if characters else ["Nenhum personagem"]))
char_menu.pack(pady=5)

action_frame = Frame(root)
action_frame.pack(pady=10)
Button(action_frame, text="Detalhar Personagem", command=detail_character).pack(side="left", padx=5)
Button(action_frame, text="Excluir Personagem", command=delete_character).pack(side="left", padx=5)
Button(action_frame, text="Batalha contra Bot", command=start_battle_versus_bot).pack(side="left", padx=5)
Button(action_frame, text="Backup Manual", command=backup_database).pack(side="left", padx=5)

# Inicia o agendamento dos backups automáticos
schedule_backup()

root.mainloop()
