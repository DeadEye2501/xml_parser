import customtkinter as ctk
from tkinter import filedialog
from lxml import etree
import ctypes
import copy
import ast
import re
import os


class Parser:
    @staticmethod
    def find_id_tags(element):
        for child in element:
            if child.tag.split('}')[1].startswith('Ид'):
                return child.tag.split('}')[1]
        return False

    def iterate_elements(self, app, element, data, namespaces, id_tag_prev=None):
        tag = element.tag.split('}')[1]
        if len(list(element)) > 0:
            id_val = None
            if element.find('ns:Ид', namespaces) is not None:
                id_tag = 'Ид'
                id_val = element.find('ns:Ид', namespaces).text
            elif id_tag := self.find_id_tags(element):
                id_val = element.find(f'ns:{id_tag}', namespaces).text
            elif tag == 'ЗначениеРеквизита' and element.find('ns:Наименование', namespaces) is not None\
                    and element.find('ns:Значение', namespaces) is not None:
                data[element.find('ns:Наименование', namespaces).text] = element.find('ns:Значение', namespaces).text
                return
            if id_val:
                data[id_val] = {}
                for child in element:
                    self.iterate_elements(app, child, data[id_val], namespaces, id_tag)
            else:
                data[tag] = {}
                for child in element:
                    self.iterate_elements(app, child, data[tag], namespaces, id_val)
        else:
            if tag == id_tag_prev:
                return
            if element.text and re.search(r'[а-яА-Яa-zA-Z0-9]', element.text):
                data[tag] = element.text
            elif element.attrib:
                data[tag] = element.attrib

    def is_empty(self, dct):
        if not isinstance(dct, dict):
            return True
        if not dct:
            return True
        return all(self.is_empty(v) for v in dct.values())

    def comparison(self, app, dct1, dct2, diff, options, outer_scope=True):
        for key, value in dct1.items():
            if not diff.get(key):
                if diff.get(key) == {} and dct2.get(key) == {}:
                    del diff[key]
                    if dct2.get(key):
                        del dct2[key]
                continue
            if isinstance(value, dict):
                if dct2.get(key):
                    self.comparison(app, value, dct2[key], diff[key], options, outer_scope=False)
                    if not diff[key]:
                        del diff[key]
                        del dct2[key]
                elif outer_scope and options[0] and self.is_empty(dct2.get(key)):
                    del diff[key]
            else:
                if not diff[key]:
                    del diff[key]
                    if dct2.get(key):
                        del dct2[key]
                    continue
                if options[1]:
                    if key == 'ДатаИзменения':
                        del diff[key]
                        if dct2.get(key):
                            del dct2[key]
                        continue
                if options[2]:
                    if key in ('Представление', 'ЦенаЗаЕдиницу', 'Количество'):
                        del diff[key]
                        if dct2.get(key):
                            del dct2[key]
                        continue
                if options[3]:
                    if key in ('ВидМаркировки', 'ВариантОграниченияСертификата'):
                        del diff[key]
                        if dct2.get(key):
                            del dct2[key]
                        continue
                if dct2.get(key):
                    new_dct2_key, new_val = str(dct2[key]), str(value)
                    if options[4]:
                        new_dct2_key, new_val = new_dct2_key.strip(), new_val.strip()
                    if options[5]:
                        new_dct2_key = re.sub(r'\s+', ' ', str(new_dct2_key))
                        new_val = re.sub(r'\s+', ' ', str(new_val))
                    if options[6]:
                        new_dct2_key, new_val = new_dct2_key.lower(), new_val.lower()
                    if new_dct2_key == new_val:
                        del diff[key]
                        del dct2[key]
                        continue

    def write_data(self, app, dct1, dct2, tab=0):
        t = '\t'
        for key, value in dct1.items():
            if tab == 0:
                app.update_table(f'{"-" * 250}\n')
            app.update_table(f'{t}{t * tab}{key}\n')
            if not dct2.get(key):
                dct2[key] = {}
            if isinstance(value, dict):
                self.write_data(app, dct1[key], dct2[key], tab=tab + 1)
            else:
                app.update_table(f'old {t}{t * (tab + 1)}"{value}"\n')
                if dct2.get(key):
                    app.update_table(f'new {t}{t * (tab + 1)}"{dct2[key]}"\n')
                else:
                    app.update_table(f'new {t}{t * (tab + 1)}*\n')

    def export_data(self, app, file, dct1, dct2, tab=0):
        t = '\t'
        for key, value in dct1.items():
            if tab == 0:
                file.write(f'{"-" * 100}\n')
            file.write(f'{t}{t * tab}{key}\n')
            if not dct2.get(key):
                dct2[key] = {}
            if isinstance(value, dict):
                self.export_data(app, file, dct1[key], dct2[key], tab=tab + 1)
            else:
                file.write(f'old {t * (tab + 1)}"{value}"\n')
                if dct2.get(key):
                    file.write(f'new {t * (tab + 1)}"{dct2[key]}"\n')
                else:
                    file.write(f'new {t * (tab + 1)}*\n')

    def parse_data(self, app, files, options, namespaces):
        data = {0: {}, 1: {}}
        namespaces = {'ns': 'urn:1C.ru:commerceml_210'} if not namespaces else ast.literal_eval(namespaces)
        for i, file in enumerate(files):
            with open(file, 'r', encoding='utf-8') as f:
                xml_content = f.read()
                root = etree.fromstring(xml_content)
                skip = False
                for lst in app.data_skip.values():
                    element = None
                    for j, value in enumerate(lst):
                        if not j:
                            element = root.find(f'ns:{value}', namespaces)
                        else:
                            element = element.find(f'ns:{value}', namespaces)
                        if element is None:
                            break
                    if element is not None:
                        for child in element:
                            self.iterate_elements(app, child, data[i], namespaces)
                        break
                if not skip:
                    for element in root:
                        self.iterate_elements(app, element, data[i], namespaces)
        diff = copy.deepcopy(data[0])
        self.comparison(app, data[0], data[1], diff, options)
        return data, diff

    def compare(self, app, files, options, namespaces=None):
        data, diff = self.parse_data(app, files, options, namespaces)
        app.update_table(f'{len(diff)} // {len(data[0])}\n')
        self.write_data(app, diff, data[1])
        app.data = (data, diff, options)

    def export(self, app, folder_path, files, options, namespaces=None):
        if app.data and app.data[2] == options:
            data, diff = app.data[0], app.data[1]
        else:
            data, diff = self.parse_data(app, files, options, namespaces)
        file_path = os.path.join(folder_path, "results.txt")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f'{len(diff)} // {len(data[0])}\n')
            self.export_data(app, f, diff, data[1])


class XMLCompareApp:
    def __init__(self, master):
        self.master = master
        self.master.geometry('1230x640')
        self.master.title('XML Compare')
        self.data_skip = {
            'offers': ('ПакетПредложений', 'Предложения'),
            'import': ('Каталог', 'Товары')
        }
        self.data = None
        self.parser = Parser()

        self.checkbox_texts = (
            'отсутствующую номенклатуру',
            'различие по датам',
            'цены и остатки',
            'сертификаты',
            'пробелы по краям',
            'пробелы в центре',
            'регистр'
        )
        self.checkbox_vars = [ctk.BooleanVar(value=True) for _ in range(len(self.checkbox_texts))]
        self.checkboxes = []

        icon_path = 'XML Compare.ico'
        if os.path.exists(icon_path):
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('XML Compare')
                self.master.iconbitmap(icon_path)
            except Exception as e:
                pass

        self.create_action_buttons_and_log(self.master)
        self.file1_entry = self.create_input_row(self.master, 'Путь к старому файлу...')
        self.file2_entry = self.create_input_row(self.master, 'Путь к новому файлу...')
        self.create_checkboxes(self.master)
        self.create_input_namespaces(self.master)
        self.create_table(self.master)

    def create_input_row(self, parent, placeholder_text):
        entry_frame = ctk.CTkFrame(parent)
        entry_frame.pack(fill=ctk.X, padx=20, pady=(10, 0))

        entry = ctk.CTkEntry(entry_frame, placeholder_text=placeholder_text)
        entry.pack(side=ctk.LEFT, fill=ctk.X, expand=True)

        def select_file():
            file_path = filedialog.askopenfilename(title='Выберите файл')
            entry.delete(0, ctk.END)
            entry.insert(0, file_path)

        button = ctk.CTkButton(
            entry_frame,
            text='Выбрать файл',
            command=select_file,
            fg_color='#b55b00',
            hover_color='#e38800'
        )
        button.pack(side=ctk.RIGHT, padx=(10, 0))
        return entry

    def create_action_buttons_and_log(self, parent):
        action_frame = ctk.CTkFrame(parent)
        action_frame.pack(fill=ctk.X, padx=20, pady=(10, 0))

        self.log_entry = ctk.CTkEntry(
            action_frame,
            placeholder_text='',
            state='disabled',
            corner_radius=5,
            fg_color='#4a4a4a',
            text_color='white',
            border_width=0,
        )
        self.log_entry.pack(side=ctk.LEFT, fill=ctk.X, expand=True)
        self.update_log('Выберите файлы...')

        compare_button = ctk.CTkButton(
            action_frame,
            text='Сравнить',
            fg_color='#b55b00',
            hover_color='#e38800',
            command=self.compare_files
        )
        compare_button.pack(side=ctk.RIGHT, padx=(10, 0))

        export_button = ctk.CTkButton(
            action_frame,
            text='Экспортировать',
            fg_color='#b55b00',
            hover_color='#e38800',
            command=self.export_files
        )
        export_button.pack(side=ctk.RIGHT, padx=(10, 0))

    def create_input_namespaces(self, parent):
        entry_frame = ctk.CTkFrame(parent)
        entry_frame.pack(fill=ctk.X, padx=20, pady=(10, 0))

        self.namespaces = ctk.CTkEntry(entry_frame, placeholder_text="Введите namespaces (если необходимо) по "
                                                                     "умолчанию: {'ns': 'urn:1C.ru:commerceml_210'}")
        self.namespaces.pack(side=ctk.LEFT, fill=ctk.X, expand=True)

    def create_checkboxes(self, parent):
        checkbox_frame = ctk.CTkFrame(parent)
        checkbox_frame.pack(anchor='w', padx=(20, 0), pady=(10, 0))

        label = ctk.CTkLabel(checkbox_frame, text="Игнорировать: ", text_color="white")
        label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        for i in range(len(self.checkbox_texts)):
            checkbox = ctk.CTkCheckBox(
                checkbox_frame,
                text=self.checkbox_texts[i],
                variable=self.checkbox_vars[i],
                fg_color='#e38800',
                hover_color='#b55b00'
            )
            checkbox.grid(row=0, column=i + 1, padx=5, pady=5, sticky='w')
            self.checkboxes.append(checkbox)

    def create_table(self, parent):
        self.text_field = ctk.CTkTextbox(parent, height=10, width=1, spacing3=10)
        self.text_field.pack(fill=ctk.BOTH, padx=20, pady=(10, 10), expand=True)
        self.text_field.configure(state='disabled')

    def check_files(self, file1, file2):
        if not file1 or not file2:
            self.update_log('Укажите файлы для сравнения')
            return False
        if not os.path.exists(file1) or not os.path.exists(file2):
            self.update_log('Один из файлов не найден')
            return False
        if not (file1.lower().endswith('.xml') and file2.lower().endswith('.xml')):
            self.update_log('Оба файла должны иметь расширение .xml')
            return False
        return True

    def compare_files(self):
        file1 = self.file1_entry.get()
        file2 = self.file2_entry.get()
        if not self.check_files(file1, file2):
            return
        options = [var.get() for var in self.checkbox_vars]
        self.text_field.configure(state='normal')
        self.text_field.delete(1.0, ctk.END)
        self.text_field.configure(state='disabled')
        self.parser.compare(self, (file1, file2), options)

    def export_files(self):
        file1 = self.file1_entry.get()
        file2 = self.file2_entry.get()
        folder_path = filedialog.askdirectory(title='Выберите папку для экспорта')
        if not self.check_files(file1, file2):
            return
        if not folder_path:
            self.update_log('Папка не выбрана')
            return
        options = [var.get() for var in self.checkbox_vars]
        self.parser.export(self, folder_path, (file1, file2), options)

    def update_log(self, message):
        self.log_entry.configure(state='normal')
        self.log_entry.delete(0, ctk.END)
        self.log_entry.insert(ctk.END, message)
        self.log_entry.configure(state='disabled')

    def update_table(self, text):
        self.text_field.configure(state='normal')
        self.text_field.insert(ctk.END, text)
        self.text_field.configure(state='disabled')


if __name__ == '__main__':
    root = ctk.CTk()
    app = XMLCompareApp(root)
    root.mainloop()
