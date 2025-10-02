import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import requests
import json
import threading
from pathlib import Path


class GitHubDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GitHub Repository Downloader")
        self.root.geometry("900x700")
        
        self.repos_list = []
        self.repo_vars = {}  # Checkbuttons dos repositórios
        self.tag_combos = {}  # Comboboxes de tags
        self.repo_tags = {}  # Cache de tags por repositório
        
        self.setup_ui()
        self.load_repos()
    
    def setup_ui(self):
        # Frame principal com scroll
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configurar grid
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        
        # === SEÇÃO TOKEN ===
        token_frame = ttk.LabelFrame(main_frame, text="GitHub Token", padding="10")
        token_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        token_frame.columnconfigure(1, weight=1)
        
        ttk.Label(token_frame, text="Token:").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.token_entry = ttk.Entry(token_frame, width=50, show="*")
        self.token_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 5))
        
        self.show_token_var = tk.BooleanVar()
        ttk.Checkbutton(token_frame, text="Mostrar", variable=self.show_token_var,
                       command=self.toggle_token_visibility).grid(row=0, column=2)
        
        # === SEÇÃO REPOSITÓRIOS ===
        repos_frame = ttk.LabelFrame(main_frame, text="Repositórios", padding="10")
        repos_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        repos_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(1, weight=1)
        
        # Canvas com scrollbar para os repositórios
        canvas = tk.Canvas(repos_frame, height=300)
        scrollbar = ttk.Scrollbar(repos_frame, orient="vertical", command=canvas.yview)
        self.repos_inner_frame = ttk.Frame(canvas)
        
        self.repos_inner_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.repos_inner_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        repos_frame.rowconfigure(0, weight=1)
        
        # === BOTÕES DE AÇÃO ===
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(buttons_frame, text="🔄 Buscar Tags", 
                  command=self.fetch_all_tags).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(buttons_frame, text="⬇️ Baixar Selecionados", 
                  command=self.start_download).pack(side=tk.LEFT)
        
        # === ÁREA DE LOG ===
        log_frame = ttk.LabelFrame(main_frame, text="Log", padding="10")
        log_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, state='disabled')
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    
    def toggle_token_visibility(self):
        if self.show_token_var.get():
            self.token_entry.config(show="")
        else:
            self.token_entry.config(show="*")
    
    def load_repos(self):
        """Carrega os repositórios do arquivo JSON"""
        try:
            with open("repo-metadata.json", "r") as f:
                self.repos_list = json.load(f)
            
            self.log(f"✅ {len(self.repos_list)} repositório(s) carregado(s)")
            self.create_repo_checkboxes()
        except FileNotFoundError:
            self.log("❌ Arquivo repo-metadata.json não encontrado!")
            messagebox.showerror("Erro", "Arquivo repo-metadata.json não encontrado!")
        except json.JSONDecodeError:
            self.log("❌ Erro ao ler repo-metadata.json!")
            messagebox.showerror("Erro", "Erro ao ler repo-metadata.json!")
    
    def create_repo_checkboxes(self):
        """Cria os checkboxes e comboboxes para cada repositório"""
        for idx, repo_info in enumerate(self.repos_list):
            owner = repo_info.get("repo_owner")
            repo = repo_info.get("repo_name")
            repo_key = f"{owner}/{repo}"
            
            # Frame para cada repositório
            repo_frame = ttk.Frame(self.repos_inner_frame)
            repo_frame.grid(row=idx, column=0, sticky=(tk.W, tk.E), pady=5, padx=5)
            repo_frame.columnconfigure(1, weight=1)
            
            # Checkbox
            var = tk.BooleanVar()
            self.repo_vars[repo_key] = var
            check = ttk.Checkbutton(repo_frame, text=repo_key, variable=var)
            check.grid(row=0, column=0, sticky=tk.W)
            
            # Label de status
            status_label = ttk.Label(repo_frame, text="", foreground="gray")
            status_label.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
            
            # Combobox para tags (inicialmente desabilitado)
            tag_combo = ttk.Combobox(repo_frame, state="disabled", width=30)
            tag_combo.grid(row=0, column=2, sticky=tk.E, padx=(10, 0))
            tag_combo.set("Clique em 'Buscar Tags'")
            
            self.tag_combos[repo_key] = {
                'combo': tag_combo,
                'status': status_label
            }
    
    def fetch_all_tags(self):
        """Busca as tags de todos os repositórios selecionados"""
        token = self.token_entry.get().strip()
        if not token:
            messagebox.showwarning("Aviso", "Por favor, insira o GitHub Token!")
            return
        
        selected = [key for key, var in self.repo_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("Aviso", "Selecione pelo menos um repositório!")
            return
        
        self.log("🔍 Buscando tags...")
        threading.Thread(target=self._fetch_tags_thread, args=(selected, token), daemon=True).start()
    
    def _fetch_tags_thread(self, selected_repos, token):
        """Thread para buscar tags sem travar a interface"""
        for repo_key in selected_repos:
            owner, repo = repo_key.split("/")
            self.update_status(repo_key, "Buscando...")
            
            tags = self.get_all_tags(owner, repo, token)
            
            if tags:
                self.repo_tags[repo_key] = tags
                tag_names = [tag['name'] for tag in tags]
                
                # Atualizar UI na thread principal
                self.root.after(0, self._update_combo, repo_key, tag_names)
                self.log(f"✅ {repo_key}: {len(tags)} tag(s) encontrada(s)")
            else:
                self.root.after(0, self._update_combo, repo_key, [])
                self.log(f"⚠️ {repo_key}: Nenhuma tag encontrada")
    
    def _update_combo(self, repo_key, tag_names):
        """Atualiza o combobox com as tags (executado na thread principal)"""
        combo_info = self.tag_combos[repo_key]
        combo = combo_info['combo']
        status = combo_info['status']
        
        if tag_names:
            combo['values'] = tag_names
            combo.current(0)
            combo['state'] = 'readonly'
            status.config(text=f"({len(tag_names)} tags)", foreground="green")
        else:
            combo.set("Nenhuma tag")
            combo['state'] = 'disabled'
            status.config(text="(sem tags)", foreground="red")
    
    def update_status(self, repo_key, text):
        """Atualiza o status de um repositório"""
        combo_info = self.tag_combos[repo_key]
        status = combo_info['status']
        self.root.after(0, lambda: status.config(text=text, foreground="blue"))
    
    def get_all_tags(self, owner, repo, token):
        """Obtém todas as tags do repositório"""
        url = f"https://api.github.com/repos/{owner}/{repo}/tags"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception as e:
            self.log(f"❌ Erro ao buscar tags: {str(e)}")
            return None
    
    def start_download(self):
        """Inicia o download dos repositórios selecionados"""
        token = self.token_entry.get().strip()
        if not token:
            messagebox.showwarning("Aviso", "Por favor, insira o GitHub Token!")
            return
        
        selected = [key for key, var in self.repo_vars.items() if var.get()]
        if not selected:
            messagebox.showwarning("Aviso", "Selecione pelo menos um repositório!")
            return
        
        # Verificar se há tags selecionadas
        downloads = []
        for repo_key in selected:
            combo = self.tag_combos[repo_key]['combo']
            tag_name = combo.get()
            
            if tag_name and tag_name != "Clique em 'Buscar Tags'" and tag_name != "Nenhuma tag":
                owner, repo = repo_key.split("/")
                downloads.append((owner, repo, tag_name))
        
        if not downloads:
            messagebox.showwarning("Aviso", "Nenhuma tag válida selecionada!")
            return
        
        self.log(f"\n📦 Iniciando download de {len(downloads)} repositório(s)...")
        threading.Thread(target=self._download_thread, args=(downloads, token), daemon=True).start()
    
    def _download_thread(self, downloads, token):
        """Thread para fazer os downloads"""
        repos_dir = Path("repos")
        repos_dir.mkdir(exist_ok=True)
        
        for owner, repo, tag_name in downloads:
            self.log(f"\n{'='*60}")
            self.log(f"Repositório: {owner}/{repo}")
            self.log(f"Tag: {tag_name}")
            self.log(f"{'='*60}")
            
            success = self.download_zip(owner, repo, tag_name, token, repos_dir)
            
            if success:
                self.log(f"✅ {repo} baixado com sucesso!")
            else:
                self.log(f"❌ Falha ao baixar {repo}")
        
        self.log(f"\n✨ Processo concluído! Arquivos em: {repos_dir.absolute()}")
        self.root.after(0, lambda: messagebox.showinfo("Concluído", "Downloads finalizados!"))
    
    def download_zip(self, owner, repo, tag_name, token, output_dir):
        """Baixa o source code zip da tag"""
        url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{tag_name}"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        output_file = output_dir / f"{repo}-{tag_name}.zip"
        
        self.log(f"⬇️ Baixando {repo} ({tag_name}) ...")
        
        try:
            response = requests.get(url, headers=headers, stream=True)
            
            if response.status_code == 200:
                with open(output_file, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                return True
            else:
                self.log(f"⚠️ Erro {response.status_code}: {response.text}")
                return False
        except Exception as e:
            self.log(f"❌ Erro: {str(e)}")
            return False
    
    def log(self, message):
        """Adiciona mensagem ao log"""
        def _log():
            self.log_text.config(state='normal')
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state='disabled')
        
        self.root.after(0, _log)


def main():
    root = tk.Tk()
    app = GitHubDownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()